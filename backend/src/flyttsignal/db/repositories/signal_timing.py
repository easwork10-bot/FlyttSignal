import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    Event,
    RentalListing,
    RentalListingRevision,
    SignalEvidence,
)
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.resolved_timing import (
    ResolvedSignalTiming,
    TimingReadMode,
)
from flyttsignal.domains.signals.timing import (
    ResolvedTimingFact,
    TimingFact,
    TimingFactType,
    resolve_timing_fact,
    timing_not_applicable,
    timing_unavailable,
)

_RENTAL_TIMING_TYPES = {
    SignalType.LIKELY_TENANT_MOVE_OUT,
    SignalType.NEW_BUILD_MOVE_IN,
    SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE,
    SignalType.POTENTIAL_NEW_BUILD_MOVE_IN,
    SignalType.LIKELY_RENTAL_TURNOVER,
}
_FACT_TYPES = (
    TimingFactType.ADVERTISED_AVAILABLE_FROM,
    TimingFactType.APPLICATION_DEADLINE,
)


class SignalTimingRepository:
    """Resolve current or historically provable listing timing for signals."""

    def __init__(self, session: Session):
        self.session = session

    def current_for_signals(
        self, signal_types: dict[uuid.UUID, SignalType]
    ) -> dict[uuid.UUID, ResolvedSignalTiming]:
        return self._resolve(signal_types=signal_types, as_of=None)

    def as_of_for_signals(
        self,
        signal_types: dict[uuid.UUID, SignalType],
        *,
        as_of: datetime,
    ) -> dict[uuid.UUID, ResolvedSignalTiming]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("signal timing as_of must be timezone-aware")
        return self._resolve(signal_types=signal_types, as_of=as_of)

    def _resolve(
        self,
        *,
        signal_types: dict[uuid.UUID, SignalType],
        as_of: datetime | None,
    ) -> dict[uuid.UUID, ResolvedSignalTiming]:
        result: dict[uuid.UUID, ResolvedSignalTiming] = {}
        applicable_ids = {
            signal_id
            for signal_id, signal_type in signal_types.items()
            if signal_type in _RENTAL_TIMING_TYPES
        }
        for signal_id in signal_types.keys() - applicable_ids:
            result[signal_id] = _not_applicable(as_of)
        if not applicable_ids:
            return result

        links = self._listing_links(signal_ids=applicable_ids, as_of=as_of)
        listing_ids = {listing.id for rows in links.values() for listing in rows}
        revisions = self._effective_revisions(listing_ids=listing_ids, as_of=as_of)

        for signal_id in applicable_ids:
            facts: list[TimingFact] = []
            warnings: set[str] = set()
            linked = links.get(signal_id, ())
            for listing in linked:
                revision = revisions.get(listing.id)
                if revision is not None:
                    if revision.listing_status != "ACTIVE":
                        warnings.add("LISTING_NOT_ACTIVE")
                        continue
                    facts.extend(_revision_facts(revision))
                elif as_of is None:
                    warnings.add("CURRENT_PROJECTION_FALLBACK")
                    if listing.status != "ACTIVE":
                        warnings.add("LISTING_NOT_ACTIVE")
                        continue
                    facts.extend(_projection_facts(listing))
                else:
                    warnings.add("NO_PROVABLE_AS_OF_REVISION")

            if as_of is not None and not facts:
                resolved = tuple(timing_unavailable(fact_type) for fact_type in _FACT_TYPES)
            else:
                resolved = tuple(
                    resolve_timing_fact(tuple(facts), fact_type=fact_type)
                    for fact_type in _FACT_TYPES
                )
            result[signal_id] = ResolvedSignalTiming(
                primary=resolved[0],
                facts=resolved,
                mode=TimingReadMode.AS_OF if as_of else TimingReadMode.CURRENT,
                as_of=as_of,
                warnings=tuple(sorted(warnings)),
            )
        return result

    def _listing_links(
        self, *, signal_ids: set[uuid.UUID], as_of: datetime | None
    ) -> dict[uuid.UUID, tuple[RentalListing, ...]]:
        query = (
            select(SignalEvidence.signal_id, RentalListing)
            .join(Event, Event.id == SignalEvidence.event_id)
            .join(
                RentalListing,
                (RentalListing.raw_item_id == Event.raw_item_id)
                & (RentalListing.is_historical == Event.is_historical),
            )
            .where(SignalEvidence.signal_id.in_(signal_ids))
        )
        if as_of is None:
            query = query.where(SignalEvidence.superseded_at.is_(None))
        else:
            query = query.where(
                SignalEvidence.valid_from <= as_of,
                (SignalEvidence.superseded_at.is_(None)) | (SignalEvidence.superseded_at > as_of),
            )
        grouped: dict[uuid.UUID, dict[uuid.UUID, RentalListing]] = defaultdict(dict)
        for signal_id, listing in self.session.execute(query):
            grouped[signal_id][listing.id] = listing
        return {signal_id: tuple(by_id.values()) for signal_id, by_id in grouped.items()}

    def _effective_revisions(
        self, *, listing_ids: set[uuid.UUID], as_of: datetime | None
    ) -> dict[uuid.UUID, RentalListingRevision]:
        if not listing_ids:
            return {}
        query = select(RentalListingRevision).where(
            RentalListingRevision.listing_id.in_(listing_ids)
        )
        if as_of is not None:
            query = query.where(RentalListingRevision.valid_from <= as_of)
        query = query.order_by(
            RentalListingRevision.listing_id,
            RentalListingRevision.valid_from.desc(),
            RentalListingRevision.revision_number.desc(),
        )
        effective: dict[uuid.UUID, RentalListingRevision] = {}
        for revision in self.session.scalars(query):
            effective.setdefault(revision.listing_id, revision)
        return effective


def _revision_facts(revision: RentalListingRevision) -> tuple[TimingFact, ...]:
    return (
        TimingFact(
            TimingFactType.ADVERTISED_AVAILABLE_FROM,
            revision.available_from,
            revision.id,
        ),
        TimingFact(
            TimingFactType.APPLICATION_DEADLINE,
            revision.application_deadline,
            revision.id,
        ),
    )


def _projection_facts(listing: RentalListing) -> tuple[TimingFact, ...]:
    return (
        TimingFact(
            TimingFactType.ADVERTISED_AVAILABLE_FROM,
            listing.available_from,
            listing.raw_item_id,
        ),
        TimingFact(
            TimingFactType.APPLICATION_DEADLINE,
            listing.application_deadline,
            listing.raw_item_id,
        ),
    )


def _not_applicable(as_of: datetime | None) -> ResolvedSignalTiming:
    facts: tuple[ResolvedTimingFact, ...] = tuple(
        timing_not_applicable(fact_type) for fact_type in _FACT_TYPES
    )
    return ResolvedSignalTiming(
        primary=facts[0],
        facts=facts,
        mode=TimingReadMode.AS_OF if as_of else TimingReadMode.CURRENT,
        as_of=as_of,
    )
