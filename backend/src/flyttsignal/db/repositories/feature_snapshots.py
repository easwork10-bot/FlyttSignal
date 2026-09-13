"""Persistence boundary for deterministic signal feature snapshots."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from flyttsignal.db.models import (
    Address,
    Event,
    ListingMeasurement,
    Property,
    RawItem,
    RentalListing,
    RentalListingClassification,
    Signal,
    SignalEvidence,
    SignalFeatureSnapshot,
    SignalOutcome,
    Source,
    SourceRun,
)
from flyttsignal.domains.events.models import EventType
from flyttsignal.domains.properties.matching import resolve_current_property_match
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.snapshots import (
    FEATURE_SCHEMA_REVISION,
    FeatureSnapshot,
    FeatureValue,
    missing,
    present,
    scalar,
    unavailable,
    value_set,
)

STOCKHOLM = ZoneInfo("Europe/Stockholm")


@dataclass(frozen=True)
class PersistedFeatureSnapshot:
    id: uuid.UUID
    payload_hash: str
    captured_at: datetime
    snapshot: FeatureSnapshot


class FeatureSnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def build_current(
        self, *, city_id: int, as_of_date: date, captured_at: datetime
    ) -> list[FeatureSnapshot]:
        local_capture_date = captured_at.astimezone(STOCKHOLM).date()
        if as_of_date != local_capture_date:
            raise ValueError(
                "current-state snapshots must use the Stockholm capture date; "
                "historical replay requires an already persisted snapshot"
            )

        held = aliased(Signal)
        held_property = (
            select(held.id)
            .where(
                held.property_id == Signal.property_id,
                held.superseded_at.is_(None),
                held.signal_type.in_(
                    (SignalType.LIKELY_TENANT_MOVE_OUT, SignalType.NEW_BUILD_MOVE_IN)
                ),
            )
            .exists()
        )
        rows = self.session.execute(
            select(Signal, Property, Address, Event, RentalListing, Source.key)
            .join(Property, Property.id == Signal.property_id)
            .join(Address, Address.id == Property.address_id)
            .join(SignalEvidence, SignalEvidence.signal_id == Signal.id)
            .join(Event, Event.id == SignalEvidence.event_id)
            .join(
                RentalListing,
                (RentalListing.raw_item_id == Event.raw_item_id)
                & (RentalListing.is_historical == Event.is_historical),
            )
            .join(RawItem, RawItem.id == Event.raw_item_id)
            .join(Source, Source.id == Event.source_id)
            .where(
                Signal.status == "ACTIVE",
                Signal.current(),
                # Current rental scoring admits factual listing evidence only.
                # Held lineages and historical captures remain untouched.
                ~held_property,
                (
                    (Signal.signal_type == SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE)
                    & RentalListing.new_construction.is_not(True)
                    | (Signal.signal_type == SignalType.POTENTIAL_NEW_BUILD_MOVE_IN)
                    & RentalListing.new_construction.is_(True)
                ),
                Event.event_type == EventType.RENTAL_LISTED,
                Event.is_historical.is_(False),
                Event.observed_at <= captured_at,
                Event.property_id == Signal.property_id,
                RentalListing.property_id == Signal.property_id,
                RentalListing.source_id == Event.source_id,
                RawItem.source_id == Event.source_id,
                RawItem.source_item_id == RentalListing.source_item_id,
                RawItem.raw_payload.is_not(None),
                RawItem.content_hash.is_not(None),
                SignalEvidence.valid_from <= captured_at,
                (
                    SignalEvidence.superseded_at.is_(None)
                    | (SignalEvidence.superseded_at > captured_at)
                ),
                (RentalListing.data_mode == "live") & RentalListing.is_historical.is_(False),
                Address.city_id == city_id,
            )
            .order_by(Signal.id, Event.id)
        ).all()
        if not rows:
            return []

        listing_ids = {row.RentalListing.id for row in rows}
        signal_ids = {row.Signal.id for row in rows}
        source_ids = {row.Event.source_id for row in rows}
        classifications: dict[uuid.UUID, list[str]] = defaultdict(list)
        for listing_id, tag in self.session.execute(
            select(RentalListingClassification.listing_id, RentalListingClassification.tag)
            .where(RentalListingClassification.listing_id.in_(listing_ids))
            .order_by(RentalListingClassification.listing_id, RentalListingClassification.tag)
        ):
            classifications[listing_id].append(tag)

        measurements: dict[uuid.UUID, list[ListingMeasurement]] = defaultdict(list)
        for measurement in self.session.scalars(
            select(ListingMeasurement)
            .where(
                ListingMeasurement.listing_id.in_(listing_ids),
                ListingMeasurement.metric == "LEAD_TIME_DAYS",
            )
            .order_by(ListingMeasurement.listing_id, ListingMeasurement.rule_version)
        ):
            measurements[measurement.listing_id].append(measurement)

        outcomes: dict[uuid.UUID, list[str]] = defaultdict(list)
        for signal_id, outcome_type in self.session.execute(
            select(SignalOutcome.signal_id, SignalOutcome.outcome_type)
            .where(SignalOutcome.signal_id.in_(signal_ids))
            .order_by(SignalOutcome.signal_id, SignalOutcome.outcome_type)
        ):
            outcomes[signal_id].append(outcome_type)

        latest_runs: dict[uuid.UUID, SourceRun] = {}
        for run in self.session.scalars(
            select(SourceRun)
            .where(SourceRun.source_id.in_(source_ids))
            .order_by(SourceRun.source_id, SourceRun.started_at.desc(), SourceRun.id)
        ):
            latest_runs.setdefault(run.source_id, run)

        grouped: dict[uuid.UUID, list] = defaultdict(list)
        for row in rows:
            grouped[row.Signal.id].append(row)
        return [
            _build_snapshot(
                grouped[signal_id],
                classifications=classifications,
                measurements=measurements,
                outcomes=outcomes.get(signal_id, []),
                latest_runs=latest_runs,
                as_of_date=as_of_date,
            )
            for signal_id in sorted(grouped, key=str)
        ]

    def persist(self, snapshots: list[FeatureSnapshot]) -> tuple[int, int]:
        created = 0
        reused = 0
        identities = {
            (
                snapshot.signal_id,
                snapshot.schema_revision,
                snapshot.as_of_date,
                snapshot.fingerprint(),
            )
            for snapshot in snapshots
        }
        signal_ids = {identity[0] for identity in identities}
        existing = (
            {
                (signal_id, revision, as_of_date, payload_hash)
                for signal_id, revision, as_of_date, payload_hash in self.session.execute(
                    select(
                        SignalFeatureSnapshot.signal_id,
                        SignalFeatureSnapshot.feature_schema_revision,
                        SignalFeatureSnapshot.as_of_date,
                        SignalFeatureSnapshot.payload_hash,
                    ).where(SignalFeatureSnapshot.signal_id.in_(signal_ids))
                )
            }
            if signal_ids
            else set()
        )
        for snapshot in snapshots:
            payload_hash = snapshot.fingerprint()
            identity = (
                snapshot.signal_id,
                snapshot.schema_revision,
                snapshot.as_of_date,
                payload_hash,
            )
            if identity in existing:
                reused += 1
                continue
            self.session.add(
                SignalFeatureSnapshot(
                    signal_id=snapshot.signal_id,
                    feature_schema_revision=snapshot.schema_revision,
                    as_of_date=snapshot.as_of_date,
                    payload=snapshot.payload(),
                    payload_hash=payload_hash,
                )
            )
            existing.add(identity)
            created += 1
        return created, reused

    def resolve(self, snapshots: list[FeatureSnapshot]) -> list[PersistedFeatureSnapshot]:
        """Resolve exact persisted rows for a caller-supplied snapshot population."""

        if not snapshots:
            return []
        self.session.flush()
        signal_ids = {snapshot.signal_id for snapshot in snapshots}
        requested = {
            (
                snapshot.signal_id,
                snapshot.schema_revision,
                snapshot.as_of_date,
                snapshot.fingerprint(),
            ): snapshot
            for snapshot in snapshots
        }
        if len(requested) != len(snapshots):
            raise ValueError("snapshot resolution requires unique persisted identities")
        rows = self.session.scalars(
            select(SignalFeatureSnapshot)
            .where(SignalFeatureSnapshot.signal_id.in_(signal_ids))
            .order_by(SignalFeatureSnapshot.signal_id, SignalFeatureSnapshot.payload_hash)
        )
        resolved: dict[tuple, PersistedFeatureSnapshot] = {}
        for row in rows:
            identity = (
                row.signal_id,
                row.feature_schema_revision,
                row.as_of_date,
                row.payload_hash,
            )
            snapshot = requested.get(identity)
            if snapshot is None:
                continue
            restored = FeatureSnapshot.from_payload(row.payload)
            if (
                restored.fingerprint() != row.payload_hash
                or restored.signal_id != snapshot.signal_id
                or restored.as_of_date != snapshot.as_of_date
                or restored.schema_revision != snapshot.schema_revision
            ):
                raise ValueError(f"snapshot {row.id} does not match its requested payload")
            resolved[identity] = PersistedFeatureSnapshot(
                id=row.id,
                payload_hash=row.payload_hash,
                captured_at=row.captured_at,
                snapshot=restored,
            )
        missing_identities = requested.keys() - resolved.keys()
        if missing_identities:
            raise ValueError("requested feature snapshots have not been persisted")
        return [resolved[identity] for identity in sorted(resolved, key=lambda item: str(item[0]))]

    def historical(
        self,
        *,
        city_id: int,
        as_of_date: date,
        feature_schema_revision: str = FEATURE_SCHEMA_REVISION,
    ) -> list[PersistedFeatureSnapshot]:
        """Load one unambiguous persisted population for deterministic replay."""

        rows = self.session.scalars(
            select(SignalFeatureSnapshot)
            .join(Signal, Signal.id == SignalFeatureSnapshot.signal_id)
            .join(Property, Property.id == Signal.property_id)
            .join(Address, Address.id == Property.address_id)
            .where(
                Address.city_id == city_id,
                SignalFeatureSnapshot.as_of_date == as_of_date,
                SignalFeatureSnapshot.feature_schema_revision == feature_schema_revision,
            )
            .order_by(
                SignalFeatureSnapshot.signal_id,
                SignalFeatureSnapshot.payload_hash,
            )
        )
        persisted: list[PersistedFeatureSnapshot] = []
        seen_signals: set[uuid.UUID] = set()
        for row in rows:
            snapshot = FeatureSnapshot.from_payload(row.payload)
            if snapshot.signal_id != row.signal_id:
                raise ValueError(f"snapshot {row.id} payload has a different signal_id")
            if snapshot.as_of_date != row.as_of_date:
                raise ValueError(f"snapshot {row.id} payload has a different as_of_date")
            if snapshot.schema_revision != row.feature_schema_revision:
                raise ValueError(f"snapshot {row.id} payload has a different schema revision")
            if snapshot.fingerprint() != row.payload_hash:
                raise ValueError(f"snapshot {row.id} payload hash does not match")
            if row.signal_id in seen_signals:
                raise ValueError(
                    "multiple snapshots exist for one signal/date/schema; "
                    "a capture manifest is required to choose a historical population"
                )
            seen_signals.add(row.signal_id)
            persisted.append(
                PersistedFeatureSnapshot(
                    id=row.id,
                    payload_hash=row.payload_hash,
                    captured_at=row.captured_at,
                    snapshot=snapshot,
                )
            )
        return persisted


def _build_snapshot(
    rows: list,
    *,
    classifications: dict[uuid.UUID, list[str]],
    measurements: dict[uuid.UUID, list[ListingMeasurement]],
    outcomes: list[str],
    latest_runs: dict[uuid.UUID, SourceRun],
    as_of_date: date,
) -> FeatureSnapshot:
    signal = rows[0].Signal
    prop = rows[0].Property
    address = rows[0].Address
    listings = [row.RentalListing for row in rows]
    events = [row.Event for row in rows]
    available_dates = [listing.available_from for listing in listings if listing.available_from]
    measured = [
        item.value
        for listing in listings
        for item in measurements.get(listing.id, [])
        if item.status == "MEASURED"
    ]
    run_values = [
        latest_runs[event.source_id] for event in events if event.source_id in latest_runs
    ]
    match_values = [
        resolve_current_property_match(
            recorded_match=row.Event.event_metadata.get("property_match"),
            recorded_reason=row.Event.event_metadata.get("property_match_reason"),
            listing_unit_identifier=row.RentalListing.unit_identifier,
            property_unit_identifier=prop.unit_identifier,
            ownership_consistent=(
                row.RentalListing.property_id == row.Event.property_id == signal.property_id
            ),
        )
        for row in rows
    ]
    # Publisher channels are not independent evidence. Canonical provider identity is
    # the independence boundary; unknown providers cannot increase corroboration.
    independent = {
        listing.upstream_provider_key
        for listing in listings
        if listing.upstream_provider_key and listing.upstream_provider_key != "UNKNOWN"
    }
    available_offsets = [(item - as_of_date).days for item in available_dates]
    features: dict[str, FeatureValue] = {
        "event_type": scalar(
            [event.event_type for event in events], missing_reason="no linked event type"
        ),
        "classification_tags": (
            value_set([tag for listing in listings for tag in classifications.get(listing.id, [])])
            if any(classifications.get(listing.id) for listing in listings)
            else missing("no stored listing classification")
        ),
        "first_seen_at": present(min(listing.first_seen_at for listing in listings)),
        "last_seen_at": present(max(listing.last_seen_at for listing in listings)),
        "listed_at": unavailable("publisher publication date is not persisted canonically"),
        "available_from": scalar(available_dates, missing_reason="listing has no available date"),
        "application_deadline": scalar(
            [listing.application_deadline for listing in listings],
            missing_reason="listing has no application deadline",
        ),
        "lead_time_days": scalar(measured, missing_reason="no measured lead time"),
        "signal_age_days": present(
            (as_of_date - signal.created_at.astimezone(STOCKHOLM).date()).days
        ),
        "days_until_available": scalar(
            available_offsets, missing_reason="available date is missing"
        ),
        "listing_status": scalar(
            [listing.status for listing in listings], missing_reason="listing status is missing"
        ),
        "signal_status": present(signal.status),
        "consecutive_misses": scalar(
            [listing.consecutive_misses for listing in listings],
            missing_reason="listing miss count is missing",
        ),
        "outcome_types": value_set(outcomes),
        "property_match": scalar(match_values, missing_reason="property match was not recorded"),
        "unit_identifier_present": scalar(
            [bool(listing.unit_identifier) for listing in listings],
            missing_reason="unit identifier presence is unknown",
        ),
        "rooms": scalar(
            [listing.rooms for listing in listings], missing_reason="rooms are missing"
        ),
        "area_m2": scalar(
            [listing.area_m2 for listing in listings], missing_reason="area is missing"
        ),
        "property_type": (
            present(prop.property_type)
            if prop.property_type and prop.property_type != "UNKNOWN"
            else missing("property type is unknown")
        ),
        "monthly_rent": scalar(
            [listing.monthly_rent for listing in listings], missing_reason="rent is missing"
        ),
        "coordinates_present": present(
            address.geometry is not None
            or (address.latitude is not None and address.longitude is not None)
        ),
        "distance_to_service_base_km": unavailable("requires a moving-company service base"),
        "source_id": scalar(
            [event.source_id for event in events], missing_reason="source identity is missing"
        ),
        "source_item_id": scalar(
            [listing.source_item_id for listing in listings],
            missing_reason="source item identity is missing",
        ),
        "publisher_channel": scalar(
            [row.key for row in rows], missing_reason="publisher channel is missing"
        ),
        "housing_provider": scalar(
            [listing.upstream_provider_key for listing in listings],
            missing_reason="housing provider is missing",
        ),
        "snapshot_status": scalar(
            [run.snapshot_status for run in run_values],
            missing_reason="no source run is available",
        ),
        "source_run_status": scalar(
            [run.status for run in run_values], missing_reason="no source run is available"
        ),
        "evidence_count": present(len(events)),
        "independent_evidence_count": present(max(1, len(independent))),
        "contradictory_evidence_present": unavailable(
            "cross-evidence contradiction rules are not implemented"
        ),
        "parser_warnings": unavailable("parser warnings are not persisted structurally"),
    }
    return FeatureSnapshot(signal.id, as_of_date, features, FEATURE_SCHEMA_REVISION)
