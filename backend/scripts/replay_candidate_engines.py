"""Replay candidate dimensions against an existing persisted feature population."""

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import text

from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.scoring.replay import replay_snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--city-id", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        population = FeatureSnapshotRepository(session).historical(
            city_id=args.city_id, as_of_date=args.as_of
        )
        report = replay_snapshots([item.snapshot for item in population])

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "items"},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
