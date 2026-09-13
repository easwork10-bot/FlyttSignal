import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import RentalListing, RentalListingRevision
from flyttsignal.domains.listings.revisions import (
    ListingRevisionCandidate,
    ListingRevisionState,
    RentalListingRevisionFacts,
    RevisionChangeKind,
    RevisionProvenance,
    plan_listing_revision,
)


@dataclass(frozen=True)
class PersistedListingRevision:
    revision: RentalListingRevision
    created: bool


class RentalListingRevisionRepository:
    """The only application write boundary for append-only listing revisions."""

    def __init__(self, session: Session):
        self.session = session

    def append(
        self, *, listing_id: uuid.UUID, candidate: ListingRevisionCandidate
    ) -> PersistedListingRevision:
        listing = self.session.scalar(
            select(RentalListing)
            .where(RentalListing.id == listing_id)
            .with_for_update()
        )
        if listing is None:
            raise ValueError("listing revision requires an existing listing")
        if candidate.raw_item_id is not None and candidate.raw_item_id != listing.raw_item_id:
            raise ValueError("listing revision raw item does not belong to the listing")

        existing_operation = self.session.scalar(
            select(RentalListingRevision).where(
                RentalListingRevision.listing_id == listing_id,
                RentalListingRevision.operation_key == candidate.operation_key,
            )
        )
        latest = self.current(listing_id=listing_id)
        if existing_operation is not None:
            if _state(existing_operation) != _candidate_state(existing_operation, candidate):
                raise ValueError("revision operation key was already used for different facts")
            return PersistedListingRevision(existing_operation, created=False)

        planned = plan_listing_revision(_state(latest) if latest else None, candidate)
        if planned is None:
            if latest is None:
                raise RuntimeError("revision planner returned no revision without history")
            return PersistedListingRevision(latest, created=False)

        row = RentalListingRevision(
            id=planned.id,
            listing_id=listing_id,
            source_run_id=planned.source_run_id,
            raw_item_id=planned.raw_item_id,
            revision_number=planned.revision_number,
            operation_key=planned.operation_key,
            change_kind=planned.change_kind.value,
            provenance_kind=planned.provenance_kind.value,
            valid_from=planned.valid_from,
            content_hash=planned.content_hash,
            raw_payload=planned.raw_payload,
            normalization_revision=planned.facts.normalization_revision,
            normalized_payload_hash=planned.facts.fingerprint(),
            listing_status=planned.facts.listing_status,
            available_from=planned.facts.available_from,
            application_deadline=planned.facts.application_deadline,
            new_construction=planned.facts.new_construction,
            categories=list(planned.facts.categories),
            unit_identifier=planned.facts.unit_identifier,
            extra_normalized_facts=planned.facts.extra_normalized_facts,
        )
        self.session.add(row)
        self.session.flush()
        return PersistedListingRevision(row, created=True)

    def current(self, *, listing_id: uuid.UUID) -> RentalListingRevision | None:
        return self.session.scalar(
            select(RentalListingRevision)
            .where(RentalListingRevision.listing_id == listing_id)
            .order_by(
                RentalListingRevision.valid_from.desc(),
                RentalListingRevision.revision_number.desc(),
            )
            .limit(1)
        )

    def as_of(
        self, *, listing_id: uuid.UUID, as_of: datetime
    ) -> RentalListingRevision | None:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("listing revision as_of must be timezone-aware")
        return self.session.scalar(
            select(RentalListingRevision)
            .where(
                RentalListingRevision.listing_id == listing_id,
                RentalListingRevision.valid_from <= as_of,
            )
            .order_by(
                RentalListingRevision.valid_from.desc(),
                RentalListingRevision.revision_number.desc(),
            )
            .limit(1)
        )


def _state(row: RentalListingRevision) -> ListingRevisionState:
    return ListingRevisionState(
        id=row.id,
        revision_number=row.revision_number,
        operation_key=row.operation_key,
        change_kind=RevisionChangeKind(row.change_kind),
        provenance_kind=RevisionProvenance(row.provenance_kind),
        valid_from=row.valid_from,
        source_run_id=row.source_run_id,
        raw_item_id=row.raw_item_id,
        content_hash=row.content_hash,
        raw_payload=row.raw_payload,
        facts=_facts(row),
    )


def _candidate_state(
    row: RentalListingRevision, candidate: ListingRevisionCandidate
) -> ListingRevisionState:
    return ListingRevisionState(
        id=row.id,
        revision_number=row.revision_number,
        operation_key=candidate.operation_key,
        change_kind=candidate.change_kind,
        provenance_kind=candidate.provenance_kind,
        valid_from=candidate.valid_from,
        source_run_id=candidate.source_run_id,
        raw_item_id=candidate.raw_item_id,
        content_hash=candidate.content_hash,
        raw_payload=candidate.raw_payload,
        facts=candidate.facts,
    )


def _facts(row: RentalListingRevision) -> RentalListingRevisionFacts:
    return RentalListingRevisionFacts(
        listing_status=row.listing_status,
        available_from=row.available_from,
        application_deadline=row.application_deadline,
        new_construction=row.new_construction,
        categories=tuple(row.categories),
        unit_identifier=row.unit_identifier,
        extra_normalized_facts=row.extra_normalized_facts,
        normalization_revision=row.normalization_revision,
    )
