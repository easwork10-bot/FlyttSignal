"""Preview or apply a complete score run to one internal-pilot scope."""

import argparse
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from flyttsignal.db.models import ScoreActivation
from flyttsignal.db.repositories.score_activations import ScoreActivationRepository
from flyttsignal.db.session import SessionLocal

DEFAULT_REASON = (
    "Selected for internal Uppsala pilot prioritization after scenario tests, replay, "
    "bounded observation, semantic repair, and idempotent S8 verification; this is not "
    "calibrated as a household-move probability."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=uuid.UUID, required=True)
    parser.add_argument("--city-id", type=int, default=1)
    parser.add_argument("--scope-key", default="internal-pilot")
    parser.add_argument("--reason", default=DEFAULT_REASON)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace-run-id", type=uuid.UUID)
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.replace_run_id:
            rows = list(
                session.scalars(
                    select(ScoreActivation)
                    .where(
                        ScoreActivation.scope_key == args.scope_key,
                        ScoreActivation.city_id == args.city_id,
                        ScoreActivation.retired_at.is_(None),
                    )
                    .with_for_update()
                )
            )
            active_runs = {row.decision_run_id for row in rows}
            if active_runs != {args.run_id}:
                if len(rows) != 3 or active_runs != {args.replace_run_id}:
                    raise ValueError("activation replacement drift")
                for row in rows:
                    row.retired_at = datetime.now(UTC)
                session.flush()
                # The new run is validated below in this same transaction. On
                # dry-run or any failure, retirement rolls back with the session.
        result = ScoreActivationRepository(session).activate_dimension_run(
            run_id=args.run_id,
            city_id=args.city_id,
            scope_key=args.scope_key,
            decision_reason=args.reason,
            apply=args.apply,
        )
        if args.apply:
            session.commit()
    print(
        json.dumps(
            {
                "city_id": result.city_id,
                "created": result.created,
                "decision_run_id": str(result.decision_run_id),
                "definitions": {
                    dimension: str(definition_id)
                    for dimension, definition_id in sorted(result.definition_ids.items())
                },
                "mode": "apply" if args.apply else "dry-run",
                "scope_key": result.scope_key,
                "scope_type": result.scope_type,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
