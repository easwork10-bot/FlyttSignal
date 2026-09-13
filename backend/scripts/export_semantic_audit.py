"""Freeze a source-scoped audit sample in a read-only transaction."""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import text

from flyttsignal.db.session import SessionLocal

QUERY = """
SELECT s.key AS source, to_jsonb(l) AS listing, to_jsonb(r) AS raw,
       to_jsonb(p) AS property, to_jsonb(a) - 'geometry' AS address,
       COALESCE((SELECT jsonb_agg(to_jsonb(e)) FROM events e
                 WHERE e.raw_item_id=r.id), '[]') AS events,
       COALESCE((SELECT jsonb_agg(to_jsonb(sig)) FROM signals sig
                 WHERE sig.property_id=p.id), '[]') AS signals,
       COALESCE((SELECT jsonb_agg(to_jsonb(se)) FROM signal_evidence se
                 JOIN events e ON e.id=se.event_id
                 WHERE e.raw_item_id=r.id), '[]') AS signal_evidence
FROM rental_listings l JOIN sources s ON s.id=l.source_id
JOIN raw_items r ON r.id=l.raw_item_id
JOIN properties p ON p.id=l.property_id JOIN addresses a ON a.id=p.address_id
WHERE l.data_mode='live' AND a.municipality_code='0380'
ORDER BY s.key,l.source_item_id
"""


def tokens(row):
    listing = row["listing"]
    result = {
        f"status:{listing['status']}",
        f"provider:{listing['upstream_provider_key']}",
        f"date_missing:{listing['available_from'] is None}",
        f"unit_missing:{not listing['unit_identifier']}",
        f"new_build:{listing['new_construction']}",
    }
    result.update(f"category:{x}" for x in listing["categories"])
    result.update(f"match:{x['metadata'].get('property_match')}" for x in row["events"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        rows = [dict(row) for row in session.execute(text(QUERY)).mappings()]
    groups = defaultdict(list)
    for row in rows:
        groups[row["source"]].append(row)
    sample = []
    coverage = {}
    for source, candidates in sorted(groups.items()):
        covered = set()
        selected = []
        remaining = list(candidates)
        while remaining and len(selected) < 20:
            # Missing-date cases are mandatory risk cases; remaining quota covers new strata.
            row = min(
                remaining,
                key=lambda x: (
                    x["listing"]["available_from"] is not None,
                    -len(tokens(x) - covered),
                    sha256(
                        ("semantic-audit:" + source + ":" + x["listing"]["source_item_id"]).encode()
                    ).hexdigest(),
                ),
            )
            row["inclusion_reasons"] = sorted(tokens(row) - covered)
            covered.update(tokens(row))
            selected.append(row)
            remaining.remove(row)
        sample.extend(selected)
        all_tokens = set().union(*(tokens(row) for row in candidates))
        coverage[source] = {
            "unique_listings": len(candidates),
            "selected": len(selected),
            "covered": sorted(covered),
            "uncovered": sorted(all_tokens - covered),
        }
    report = {"exported_at": datetime.now(UTC).isoformat(), "coverage": coverage, "sample": sample}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    print(json.dumps({"exported_at": report["exported_at"], "coverage": coverage}))


if __name__ == "__main__":
    main()
