"""Verify listing identity projections and event/signal ownership after remediation."""

import argparse
import json

from sqlalchemy import select

from flyttsignal.db.models import Event, RentalListing, Signal, SignalEvidence, Source
from flyttsignal.db.session import SessionLocal
from flyttsignal.property_provenance.service import remediate_property_provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Restrict verification to one exact source key.")
    parser.add_argument("--active-only", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as session:
        remaining = remediate_property_provenance(
            session,
            source_key=args.source,
            active_only=args.active_only,
        )
        listing_query = (
            select(RentalListing.id, Event.id)
            .join(
                Event,
                (Event.raw_item_id == RentalListing.raw_item_id)
                & (Event.property_id != RentalListing.property_id),
            )
            .join(SignalEvidence, SignalEvidence.event_id == Event.id)
            .where(SignalEvidence.superseded_at.is_(None))
        )
        historical_query = (
            select(RentalListing.id, Event.id)
            .join(
                Event,
                (Event.raw_item_id == RentalListing.raw_item_id)
                & (Event.property_id != RentalListing.property_id),
            )
            .join(SignalEvidence, SignalEvidence.event_id == Event.id)
            .where(SignalEvidence.superseded_at.is_not(None))
        )
        signal_query = (
            select(Signal.id, Event.id)
            .join(SignalEvidence, SignalEvidence.signal_id == Signal.id)
            .join(Event, Event.id == SignalEvidence.event_id)
            .where(Signal.property_id != Event.property_id)
        )
        if args.source:
            listing_query = listing_query.join(
                Source, RentalListing.source_id == Source.id
            ).where(Source.key == args.source)
            historical_query = historical_query.join(
                Source, RentalListing.source_id == Source.id
            ).where(Source.key == args.source)
            signal_query = signal_query.join(Source, Event.source_id == Source.id).where(
                Source.key == args.source
            )
        if args.active_only:
            listing_query = listing_query.where(RentalListing.status == "ACTIVE")
            historical_query = historical_query.where(RentalListing.status == "ACTIVE")
            signal_query = signal_query.join(
                RentalListing,
                RentalListing.raw_item_id == Event.raw_item_id,
            ).where(RentalListing.status == "ACTIVE")
        listing_event_mismatches = list(
            session.execute(listing_query)
        )
        historical_mismatches = list(session.execute(historical_query))
        signal_event_mismatches = list(session.execute(signal_query))

    report = {
        "remaining_listing_updates": remaining.listing_provenance_updates,
        "remaining_actions": len(remaining.actions),
        "listing_event_property_mismatches": len(listing_event_mismatches),
        "signal_event_property_mismatches": len(signal_event_mismatches),
        "historical_superseded_event_property_differences": len(historical_mismatches),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    failure_fields = (
        "remaining_listing_updates",
        "remaining_actions",
        "listing_event_property_mismatches",
        "signal_event_property_mismatches",
    )
    if any(report[field] for field in failure_fields):
        raise SystemExit("Property provenance verification failed")


if __name__ == "__main__":
    main()
