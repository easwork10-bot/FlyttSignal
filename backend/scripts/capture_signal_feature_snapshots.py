"""Preview or persist score-agnostic feature snapshots for live signals."""

import argparse
import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.domains.signals.snapshots import FEATURE_SCHEMA_REVISION


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--city-id", type=int, default=1)
    args = parser.parse_args()
    captured_at = datetime.now(ZoneInfo("Europe/Stockholm"))
    as_of_date = captured_at.date()

    with SessionLocal() as session:
        repository = FeatureSnapshotRepository(session)
        snapshots = repository.build_current(
            city_id=args.city_id,
            as_of_date=as_of_date,
            captured_at=captured_at,
        )
        population_input = "\n".join(
            f"{snapshot.signal_id}:{snapshot.fingerprint()}" for snapshot in snapshots
        )
        states = Counter(
            value.state.value for snapshot in snapshots for value in snapshot.features.values()
        )
        created = reused = 0
        if args.apply:
            created, reused = repository.persist(snapshots)
            session.commit()

    print(
        json.dumps(
            {
                "as_of_date": as_of_date.isoformat(),
                "city_id": args.city_id,
                "created": created,
                "feature_schema_revision": FEATURE_SCHEMA_REVISION,
                "mode": "apply" if args.apply else "dry-run",
                "population_fingerprint": sha256(population_input.encode()).hexdigest(),
                "population_size": len(snapshots),
                "reused": reused,
                "value_states": dict(sorted(states.items())),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
