"""Export a validation batch as a human-review CSV template."""

import argparse
import csv
from pathlib import Path
from uuid import UUID

from flyttsignal.db.repositories.validation import ValidationRepository
from flyttsignal.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True, type=UUID)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with SessionLocal() as session:
        batch = ValidationRepository(session).batch(args.batch_id)
        if batch is None:
            raise SystemExit("validation batch not found")
        rows = sorted(
            batch.validations,
            key=lambda item: (
                item.strength_stratum or item.score_stratum or "",
                -(item.signal_strength_at_selection or item.score_at_selection or 0),
                str(item.signal_id),
            ),
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "signal_id",
                "signal_url",
                "signal_strength",
                "data_confidence",
                "timing",
                "strength_stratum",
                "legacy_score",
                "legacy_score_stratum",
                "inclusion_reasons",
                "source_keys",
                "provider_keys",
                "classification_tags",
                "verdict",
                "issue_codes",
                "notes",
                "reviewer",
            ],
        )
        writer.writeheader()
        for item in rows:
            writer.writerow(
                {
                    "signal_id": item.signal_id,
                    "signal_url": f"http://localhost:3000/signals/{item.signal_id}",
                    "signal_strength": item.signal_strength_at_selection,
                    "data_confidence": item.data_confidence_at_selection,
                    "timing": item.timing_at_selection,
                    "strength_stratum": item.strength_stratum,
                    "legacy_score": item.score_at_selection,
                    "legacy_score_stratum": item.score_stratum,
                    "inclusion_reasons": "|".join(item.inclusion_reasons),
                    "source_keys": "|".join(item.source_keys),
                    "provider_keys": "|".join(item.provider_keys),
                    "classification_tags": "|".join(item.classification_tags),
                    "verdict": item.verdict or "",
                    "issue_codes": "|".join(item.issue_codes),
                    "notes": item.notes or "",
                    "reviewer": item.reviewer or "",
                }
            )

    print(f"exported {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
