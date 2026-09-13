import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    Event,
    RentalListing,
    SignalEvidence,
    SignalOutcome,
)
from flyttsignal.domains.signals import outcomes as signal_outcomes


def record_signal_outcome(
    session: Session,
    *,
    signal_id: UUID,
    outcome_type: str,
    observed_at: datetime,
    dedupe_key: str,
    evidence: dict[str, Any],
    confidence: Decimal = Decimal("1.000"),
    listing_id: UUID | None = None,
    event_id: UUID | None = None,
) -> SignalOutcome:
    definition = signal_outcomes.OUTCOME_DEFINITIONS[outcome_type]
    row = session.scalar(
        select(SignalOutcome).where(
            SignalOutcome.signal_id == signal_id,
            SignalOutcome.outcome_type == outcome_type,
            SignalOutcome.dedupe_key == dedupe_key,
            SignalOutcome.rule_version == signal_outcomes.OUTCOME_RULE_VERSION,
        )
    )
    if row is None:
        row = SignalOutcome(
            signal_id=signal_id,
            outcome_type=outcome_type,
            dedupe_key=dedupe_key,
            rule_version=signal_outcomes.OUTCOME_RULE_VERSION,
            observed_at=observed_at,
        )
        session.add(row)
    row.subject = definition.subject
    row.verification_level = definition.verification_level
    row.confidence = confidence
    row.evidence = evidence
    row.listing_id = listing_id
    row.event_id = event_id
    return row


def _signal_links_for_listing(session: Session, listing: RentalListing) -> list[tuple[UUID, UUID]]:
    return list(
        session.execute(
            select(SignalEvidence.signal_id, Event.id)
            .join(Event, SignalEvidence.event_id == Event.id)
            .where(
                Event.raw_item_id == listing.raw_item_id,
                SignalEvidence.superseded_at.is_(None),
            )
        ).tuples()
    )


def record_listing_state_outcome(
    session: Session,
    *,
    listing: RentalListing,
    outcome_type: str,
    observed_at: datetime,
    dedupe_key: str,
    evidence: dict[str, Any],
) -> int:
    count = 0
    for signal_id, event_id in _signal_links_for_listing(session, listing):
        record_signal_outcome(
            session,
            signal_id=signal_id,
            outcome_type=outcome_type,
            observed_at=observed_at,
            dedupe_key=dedupe_key,
            evidence=evidence,
            listing_id=listing.id,
            event_id=event_id,
        )
        count += 1
    return count


def record_available_date_change(
    session: Session,
    *,
    listing: RentalListing,
    previous: date | None,
    current: date | None,
    observed_at: datetime,
    run_id: UUID,
) -> int:
    if previous == current:
        return 0
    return record_listing_state_outcome(
        session,
        listing=listing,
        outcome_type="AVAILABLE_DATE_CHANGED",
        observed_at=observed_at,
        dedupe_key=f"listing:{listing.id}:run:{run_id}",
        evidence={
            "previous_available_from": previous.isoformat() if previous else None,
            "current_available_from": current.isoformat() if current else None,
            "source_run_id": str(run_id),
            "interpretation": "advertised_date_change_only",
        },
    )


def record_cross_source_outcome(
    session: Session, *, signal_id: UUID, observed_at: datetime
) -> SignalOutcome | None:
    observations = list(
        session.execute(
            select(
                Event.source_id,
                RentalListing.upstream_provider_key,
                RentalListing.source_item_id,
                Event.raw_item_id,
            )
            .select_from(SignalEvidence)
            .join(Event, SignalEvidence.event_id == Event.id)
            .outerjoin(RentalListing, RentalListing.raw_item_id == Event.raw_item_id)
            .where(
                SignalEvidence.signal_id == signal_id,
                SignalEvidence.superseded_at.is_(None),
            )
        ).tuples()
    )
    # Publisher channels are collection paths, not independent landlord evidence.
    # One canonical provider contributes at most one corroborating observation.
    provider_observations = {
        (
            provider_key,
            source_item_id or str(raw_item_id),
        ): {
            "provider_key": provider_key,
            "source_item_id": source_item_id or str(raw_item_id),
            "publisher_source_id": str(source_id),
        }
        for source_id, provider_key, source_item_id, raw_item_id in observations
        if provider_key and provider_key != "UNKNOWN"
    }
    provider_keys = sorted({item["provider_key"] for item in provider_observations.values()})
    if len(provider_keys) < 2:
        return None
    digest = hashlib.sha256("|".join(provider_keys).encode()).hexdigest()
    publisher_source_ids = sorted(
        {item["publisher_source_id"] for item in provider_observations.values()}
    )
    return record_signal_outcome(
        session,
        signal_id=signal_id,
        outcome_type="CROSS_SOURCE_CONFIRMED",
        observed_at=observed_at,
        dedupe_key=f"publisher-sources:{digest}",
        evidence={
            "publisher_source_ids": publisher_source_ids,
            "publisher_source_count": len(publisher_source_ids),
            "canonical_provider_keys": provider_keys,
            "canonical_provider_count": len(provider_keys),
            "upstream_listing_ids": sorted(
                {item["source_item_id"] for item in provider_observations.values()}
            ),
            "interpretation": "signal_observation_corroborated_not_move_confirmed",
        },
    )
