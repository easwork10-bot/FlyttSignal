"""Preview or atomically persist a reproducible candidate dimension-score run."""

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.db.repositories.score_runs import ScoreRunRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.scoring.replay import replay_snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--city-id", type=int, default=1)
    args = parser.parse_args()
    captured_at = datetime.now(ZoneInfo("Europe/Stockholm"))
    as_of_date = captured_at.date()

    with SessionLocal() as session:
        snapshots = FeatureSnapshotRepository(session).build_current(
            city_id=args.city_id,
            as_of_date=as_of_date,
            captured_at=captured_at,
        )
        replay = replay_snapshots(snapshots)
        response = {
            "as_of_date": replay["as_of_date"],
            "city_id": args.city_id,
            "definitions": replay["definitions"],
            "feature_schema_revision": replay["feature_schema_revision"],
            "mode": "dry-run",
            "population_fingerprint": replay["population_fingerprint"],
            "population_size": replay["population_size"],
        }
        if args.apply:
            snapshot_repository = FeatureSnapshotRepository(session)
            snapshots_created, snapshots_reused = snapshot_repository.persist(snapshots)
            persisted = snapshot_repository.resolve(snapshots)
            result = ScoreRunRepository(session).persist_dimension_run(
                city_id=args.city_id,
                snapshots=persisted,
            )
            session.commit()
            response.update(
                {
                    "mode": "apply",
                    "run_id": str(result.run_id),
                    "run_created": result.created,
                    "definitions_created": result.definitions_created,
                    "evaluations_created": result.evaluations_created,
                    "definition_set_hash": result.definition_set_hash,
                    "population_fingerprint": result.population_fingerprint,
                    "snapshots_created": snapshots_created,
                    "snapshots_reused": snapshots_reused,
                }
            )

    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
