import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from flyttsignal.db.models import (
    Address,
    Event,
    Property,
    RentalListing,
    RentalListingClassification,
    Signal,
    SignalEvidence,
    Source,
    ValidationBatch,
)
from flyttsignal.db.repositories.score_activations import active_dimensions_subquery
from flyttsignal.domains.signals.validation import ValidationCandidate


class ValidationRepository:
    def __init__(self, session: Session):
        self.session = session

    def candidates(self, *, city_id: int = 1, as_of: datetime) -> list[ValidationCandidate]:
        active_dimensions = active_dimensions_subquery(
            scope_key="internal-pilot",
            city_id=city_id,
        )
        rows = self.session.execute(
            select(
                Signal.id.label("signal_id"),
                active_dimensions.c.run_id,
                active_dimensions.c.as_of_date,
                active_dimensions.c.definition_set_hash,
                active_dimensions.c.signal_strength,
                active_dimensions.c.data_confidence,
                active_dimensions.c.timing,
                RentalListing.id.label("listing_id"),
                RentalListing.property_id,
                RentalListing.upstream_provider_key,
                RentalListing.available_from,
                RentalListing.source_id,
            )
            .join(Property, Property.id == Signal.property_id)
            .join(Address, Address.id == Property.address_id)
            .join(active_dimensions, active_dimensions.c.signal_id == Signal.id)
            .join(SignalEvidence, SignalEvidence.signal_id == Signal.id)
            .join(Event, Event.id == SignalEvidence.event_id)
            .join(RentalListing, RentalListing.raw_item_id == Event.raw_item_id)
            .where(
                Signal.status == "ACTIVE",
                Signal.current(),
                SignalEvidence.valid_from <= as_of,
                (
                    SignalEvidence.superseded_at.is_(None)
                    | (SignalEvidence.superseded_at > as_of)
                ),
                RentalListing.data_mode == "live",
                RentalListing.status == "ACTIVE",
                Address.city_id == city_id,
            )
            .order_by(Signal.id, RentalListing.id)
        ).all()
        listing_ids = {row.listing_id for row in rows}
        classification_rows = (
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
        tags_by_listing: dict[uuid.UUID, set[str]] = {}
        for row in classification_rows:
            tags_by_listing.setdefault(row.listing_id, set()).add(row.tag)

        grouped: dict[uuid.UUID, dict] = {}
        for row in rows:
            item = grouped.setdefault(
                row.signal_id,
                {
                    "score_run_id": row.run_id,
                    "score_as_of_date": row.as_of_date,
                    "definition_set_hash": row.definition_set_hash,
                    "signal_strength": row.signal_strength,
                    "data_confidence": row.data_confidence,
                    "timing": row.timing,
                    "listing_ids": set(),
                    "property_ids": set(),
                    "source_ids": set(),
                    "provider_keys": set(),
                    "classification_tags": set(),
                    "missing_available_from": False,
                },
            )
            item["listing_ids"].add(row.listing_id)
            item["property_ids"].add(row.property_id)
            item["source_ids"].add(row.source_id)
            item["provider_keys"].add(row.upstream_provider_key)
            item["classification_tags"].update(tags_by_listing.get(row.listing_id, ()))
            item["missing_available_from"] |= row.available_from is None

        source_ids = {source_id for item in grouped.values() for source_id in item["source_ids"]}
        source_keys = (
            dict(
                self.session.execute(
                    select(Source.id, Source.key).where(Source.id.in_(source_ids))
                ).all()
            )
            if source_ids
            else {}
        )
        property_source_rows = self.session.execute(
            select(RentalListing.property_id, RentalListing.source_id)
            .join(Property, Property.id == RentalListing.property_id)
            .join(Address, Address.id == Property.address_id)
            .where(
                RentalListing.data_mode == "live",
                RentalListing.status == "ACTIVE",
                Address.city_id == city_id,
            )
        ).all()
        sources_by_property: dict[uuid.UUID, set[uuid.UUID]] = {}
        for row in property_source_rows:
            sources_by_property.setdefault(row.property_id, set()).add(row.source_id)
        overlap_properties = {
            property_id
            for property_id, property_sources in sources_by_property.items()
            if len(property_sources) >= 2
        }
        return [
            ValidationCandidate(
                signal_id=signal_id,
                score_run_id=item["score_run_id"],
                score_as_of_date=item["score_as_of_date"],
                definition_set_hash=item["definition_set_hash"],
                signal_strength=item["signal_strength"],
                data_confidence=item["data_confidence"],
                timing=item["timing"],
                listing_ids=tuple(sorted(item["listing_ids"], key=str)),
                property_ids=tuple(sorted(item["property_ids"], key=str)),
                source_keys=tuple(
                    sorted(source_keys[source_id] for source_id in item["source_ids"])
                ),
                provider_keys=tuple(sorted(item["provider_keys"])),
                classification_tags=tuple(sorted(item["classification_tags"])),
                missing_available_from=item["missing_available_from"],
                cross_source_property=bool(item["property_ids"] & overlap_properties),
            )
            for signal_id, item in sorted(grouped.items(), key=lambda row: str(row[0]))
        ]

    def batches(self) -> list[ValidationBatch]:
        return list(
            self.session.scalars(
                select(ValidationBatch)
                .options(selectinload(ValidationBatch.validations))
                .order_by(ValidationBatch.created_at.desc())
            ).unique()
        )

    def batch(self, batch_id: uuid.UUID) -> ValidationBatch | None:
        return self.session.scalar(
            select(ValidationBatch)
            .options(selectinload(ValidationBatch.validations))
            .where(ValidationBatch.id == batch_id)
        )

    def batch_by_name(self, name: str) -> ValidationBatch | None:
        return self.session.scalar(
            select(ValidationBatch)
            .options(selectinload(ValidationBatch.validations))
            .where(ValidationBatch.name == name)
        )
