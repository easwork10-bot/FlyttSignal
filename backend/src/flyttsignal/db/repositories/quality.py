import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    Address,
    City,
    Event,
    ListingMeasurement,
    Property,
    RentalListing,
    RentalListingClassification,
    Signal,
    SignalEvidence,
    SignalOutcome,
    Source,
    SourceRun,
)
from flyttsignal.db.repositories.score_activations import active_dimensions_subquery

ACTIVE_SCORE_SCOPE = "internal-pilot"


@dataclass(frozen=True)
class ListingQualityFact:
    listing_id: uuid.UUID
    source_id: uuid.UUID
    source_key: str
    source_name: str
    property_id: uuid.UUID
    available_from_present: bool


@dataclass(frozen=True)
class SignalQualityFact:
    signal_id: uuid.UUID
    status: str
    signal_strength: int
    created_at: datetime
    evidence_count: int
    ambiguous_match_count: int


@dataclass(frozen=True)
class OutcomeQualityFact:
    signal_id: uuid.UUID
    outcome_type: str
    subject: str
    verification_level: str


@dataclass(frozen=True)
class QualityDataset:
    city_id: int
    city_name: str
    listings: tuple[ListingQualityFact, ...]
    classified_listing_ids: frozenset[uuid.UUID]
    unknown_listing_ids: frozenset[uuid.UUID]
    measured_listing_ids: frozenset[uuid.UUID]
    usable_lead_time_values: tuple[Decimal, ...]
    signals: tuple[SignalQualityFact, ...]
    outcomes: tuple[OutcomeQualityFact, ...]
    latest_runs: dict[uuid.UUID, SourceRun]


class QualityRepository:
    """Build one bounded, read-only quality dataset for a city."""

    def __init__(self, session: Session):
        self.session = session

    def dataset(self, city_id: int = 1) -> QualityDataset | None:
        city = self.session.get(City, city_id)
        if city is None:
            return None

        listing_rows = self.session.execute(
            select(
                RentalListing.id,
                RentalListing.source_id,
                Source.key,
                Source.name,
                RentalListing.property_id,
                RentalListing.available_from.is_not(None),
            )
            .join(Source, Source.id == RentalListing.source_id)
            .join(Property, Property.id == RentalListing.property_id)
            .join(Address, Address.id == Property.address_id)
            .where(
                (RentalListing.data_mode == "live") & RentalListing.is_historical.is_(False),
                RentalListing.status == "ACTIVE",
                Address.city_id == city_id,
            )
            .order_by(RentalListing.id)
        ).all()
        listings = tuple(ListingQualityFact(*row) for row in listing_rows)
        listing_ids = [item.listing_id for item in listings]

        classifications = (
            self.session.execute(
                select(
                    RentalListingClassification.listing_id,
                    RentalListingClassification.tag,
                ).where(
                    RentalListingClassification.listing_id.in_(listing_ids),
                    RentalListingClassification.rule_version == "classification-v1",
                )
            ).all()
            if listing_ids
            else []
        )
        classified_listing_ids = frozenset(row.listing_id for row in classifications)
        unknown_listing_ids = frozenset(
            row.listing_id for row in classifications if row.tag == "UNKNOWN"
        )

        measurements = (
            self.session.execute(
                select(
                    ListingMeasurement.listing_id,
                    ListingMeasurement.status,
                    ListingMeasurement.value,
                ).where(
                    ListingMeasurement.listing_id.in_(listing_ids),
                    ListingMeasurement.metric == "LEAD_TIME_DAYS",
                    ListingMeasurement.rule_version == "lead-time-v1",
                )
            ).all()
            if listing_ids
            else []
        )
        measured_listing_ids = frozenset(row.listing_id for row in measurements)
        usable_lead_time_values = tuple(
            row.value for row in measurements if row.status == "MEASURED" and row.value is not None
        )

        active_dimensions = active_dimensions_subquery(
            scope_key=ACTIVE_SCORE_SCOPE,
            city_id=city_id,
        )
        signal_rows = self.session.execute(
            select(
                Signal.id,
                Signal.status,
                active_dimensions.c.signal_strength,
                Signal.created_at,
                func.count(func.distinct(SignalEvidence.event_id)),
                func.count(func.distinct(Event.id)).filter(
                    Event.event_metadata["property_match"].as_string() == "UNCERTAIN_MATCH"
                ),
            )
            .join(Property, Property.id == Signal.property_id)
            .join(Address, Address.id == Property.address_id)
            .join(active_dimensions, active_dimensions.c.signal_id == Signal.id)
            .join(SignalEvidence, SignalEvidence.signal_id == Signal.id)
            .join(Event, Event.id == SignalEvidence.event_id)
            .join(
                RentalListing,
                (
                    (RentalListing.raw_item_id == Event.raw_item_id)
                    & (RentalListing.is_historical == Event.is_historical)
                )
                & ((RentalListing.data_mode == "live") & RentalListing.is_historical.is_(False)),
            )
            .where(
                Address.city_id == city_id,
                SignalEvidence.superseded_at.is_(None),
                Signal.current(),
            )
            .group_by(Signal.id, active_dimensions.c.signal_strength)
            .order_by(Signal.id)
        ).all()
        signals = tuple(SignalQualityFact(*row) for row in signal_rows)
        signal_ids = [item.signal_id for item in signals]

        outcome_rows = (
            self.session.execute(
                select(
                    SignalOutcome.signal_id,
                    SignalOutcome.outcome_type,
                    SignalOutcome.subject,
                    SignalOutcome.verification_level,
                ).where(
                    SignalOutcome.signal_id.in_(signal_ids),
                    SignalOutcome.rule_version == "outcome-v1",
                )
            ).all()
            if signal_ids
            else []
        )
        outcomes = tuple(OutcomeQualityFact(*row) for row in outcome_rows)

        source_ids = {item.source_id for item in listings}
        latest_runs: dict[uuid.UUID, SourceRun] = {}
        if source_ids:
            latest_started = (
                select(
                    SourceRun.source_id,
                    func.max(SourceRun.started_at).label("started_at"),
                )
                .where(SourceRun.source_id.in_(source_ids))
                .group_by(SourceRun.source_id)
                .subquery()
            )
            runs = self.session.scalars(
                select(SourceRun).join(
                    latest_started,
                    (latest_started.c.source_id == SourceRun.source_id)
                    & (latest_started.c.started_at == SourceRun.started_at),
                )
            )
            latest_runs = {run.source_id: run for run in runs}

        return QualityDataset(
            city_id=city.id,
            city_name=city.name,
            listings=listings,
            classified_listing_ids=classified_listing_ids,
            unknown_listing_ids=unknown_listing_ids,
            measured_listing_ids=measured_listing_ids,
            usable_lead_time_values=usable_lead_time_values,
            signals=signals,
            outcomes=outcomes,
            latest_runs=latest_runs,
        )
