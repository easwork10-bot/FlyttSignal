"""Preview or persist only outcomes provable from retained live data."""

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import distinct, func, select

from flyttsignal.db.models import Event, RentalListing, SignalEvidence, SignalOutcome
from flyttsignal.db.session import SessionLocal
from flyttsignal.outcomes.service import (
    OUTCOME_RULE_VERSION,
    record_cross_source_outcome,
    record_listing_state_outcome,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as session:
        cross_source = list(
            session.execute(
                select(SignalEvidence.signal_id, func.max(Event.observed_at))
                .join(Event, Event.id == SignalEvidence.event_id)
                .where(SignalEvidence.superseded_at.is_(None))
                .group_by(SignalEvidence.signal_id)
                .having(func.count(distinct(Event.source_id)) >= 2)
                .order_by(SignalEvidence.signal_id)
            ).tuples()
        )
        removed = list(
            session.scalars(
                select(RentalListing)
                .where(
                    RentalListing.data_mode == "live",
                    RentalListing.status == "REMOVED",
                    RentalListing.removed_at.is_not(None),
                )
                .order_by(RentalListing.id)
            )
        )

        if args.apply:
            for signal_id, observed_at in cross_source:
                record_cross_source_outcome(
                    session,
                    signal_id=signal_id,
                    observed_at=observed_at or datetime.now(UTC),
                )
            for listing in removed:
                record_listing_state_outcome(
                    session,
                    listing=listing,
                    outcome_type="LISTING_REMOVED",
                    observed_at=listing.removed_at,
                    dedupe_key=f"listing:{listing.id}:removed:{listing.removed_at.isoformat()}",
                    evidence={
                        "listing_id": str(listing.id),
                        "removed_at": listing.removed_at.isoformat(),
                        "interpretation": "listing_disappearance_only_not_move_confirmed",
                        "origin": "retained_listing_state_backfill",
                    },
                )
            session.commit()

        persisted_count = session.scalar(
            select(func.count(SignalOutcome.id)).where(
                SignalOutcome.rule_version == OUTCOME_RULE_VERSION
            )
        )

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "eligible_cross_source_signals": len(cross_source),
                "eligible_removed_listings": len(removed),
                "persisted_outcome_v1_rows": persisted_count or 0,
                "historical_date_changes_backfilled": 0,
                "historical_relistings_backfilled": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
