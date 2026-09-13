from collections import defaultdict
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    Event,
    Property,
    RawItem,
    RentalListing,
    Signal,
    SignalEvidence,
    Source,
)
from flyttsignal.domains.properties.identity import PropertyIdentity
from flyttsignal.normalization.service import normalize_item


@dataclass(frozen=True)
class ListingRecord:
    listing: RentalListing
    prop: Property
    identity: PropertyIdentity
    source_key: str


@dataclass(frozen=True)
class RepairAction:
    kind: str
    property_id: UUID
    listing_id: UUID | None
    reason: str
    details: dict

    def as_dict(self) -> dict:
        result = asdict(self)
        result["property_id"] = str(self.property_id)
        result["listing_id"] = str(self.listing_id) if self.listing_id else None
        return result


@dataclass(frozen=True)
class RemediationResult:
    mode: str
    listings_examined: int
    listing_provenance_updates: int
    actions: tuple[RepairAction, ...]

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "listings_examined": self.listings_examined,
            "listing_provenance_updates": self.listing_provenance_updates,
            "action_counts": {
                kind: sum(action.kind == kind for action in self.actions)
                for kind in sorted({action.kind for action in self.actions})
            },
            "actions": [action.as_dict() for action in self.actions],
        }


def _property_identity(prop: Property) -> PropertyIdentity:
    return PropertyIdentity(
        unit_identifier=prop.unit_identifier,
        rooms=prop.rooms,
        area_m2=prop.area_m2,
        new_construction=prop.new_construction,
    )


def _listing_identity(listing: RentalListing) -> PropertyIdentity:
    return PropertyIdentity(
        unit_identifier=listing.unit_identifier,
        rooms=listing.rooms,
        area_m2=listing.area_m2,
        new_construction=listing.new_construction,
    )


def _set_listing_identity(listing: RentalListing, identity: PropertyIdentity) -> None:
    listing.unit_identifier = identity.unit_identifier
    listing.rooms = identity.rooms
    listing.area_m2 = identity.area_m2
    listing.new_construction = identity.new_construction


def _set_property_identity(prop: Property, identity: PropertyIdentity) -> None:
    prop.unit_identifier = identity.unit_identifier
    prop.rooms = identity.rooms
    prop.area_m2 = identity.area_m2
    prop.new_construction = identity.new_construction


def _can_move_listing_evidence(session: Session, record: ListingRecord) -> bool:
    event_ids = set(
        session.scalars(
            select(Event.id).where(
                Event.raw_item_id == record.listing.raw_item_id,
                Event.property_id == record.prop.id,
            )
        )
    )
    if not event_ids:
        return False
    signal_ids = set(
        session.scalars(
            select(SignalEvidence.signal_id).where(
                SignalEvidence.event_id.in_(event_ids),
                SignalEvidence.superseded_at.is_(None),
            )
        )
    )
    for signal_id in signal_ids:
        all_evidence = set(
            session.scalars(
                select(SignalEvidence.event_id).where(
                    SignalEvidence.signal_id == signal_id,
                    SignalEvidence.superseded_at.is_(None),
                )
            )
        )
        if not all_evidence.issubset(event_ids):
            return False
    return True


def _load_records(
    session: Session,
    *,
    source_key: str | None = None,
    active_only: bool = False,
) -> list[ListingRecord]:
    query = (
        select(RentalListing, RawItem, Property, Source)
        .join(RawItem, RentalListing.raw_item_id == RawItem.id)
        .join(Property, RentalListing.property_id == Property.id)
        .join(Source, RentalListing.source_id == Source.id)
        .where(RentalListing.data_mode == "live")
    )
    if source_key is not None:
        query = query.where(Source.key == source_key)
    if active_only:
        query = query.where(RentalListing.status == "ACTIVE")
    rows = session.execute(query)
    return [
        ListingRecord(
            listing=listing,
            prop=prop,
            identity=_identity_from_raw_payload(raw.raw_payload),
            source_key=source.key,
        )
        for listing, raw, prop, source in rows
    ]


def _identity_from_raw_payload(raw_payload: dict) -> PropertyIdentity:
    item = normalize_item(raw_payload)
    return PropertyIdentity(
        unit_identifier=item.unit_identifier,
        rooms=item.rooms,
        area_m2=item.area_m2,
        new_construction=item.new_construction,
    )


def _plan_actions(session: Session, records: list[ListingRecord]) -> list[RepairAction]:
    by_property: dict[UUID, list[ListingRecord]] = defaultdict(list)
    for record in records:
        if record.listing.status != "REMOVED":
            by_property[record.prop.id].append(record)

    actions: list[RepairAction] = []
    for property_id, group in by_property.items():
        scoped_listing_ids = {record.listing.id for record in group}
        all_listing_ids = set(
            session.scalars(
                select(RentalListing.id).where(
                    RentalListing.property_id == property_id,
                    RentalListing.status != "REMOVED",
                    RentalListing.data_mode == "live",
                )
            )
        )
        if all_listing_ids != scoped_listing_ids:
            actions.append(
                RepairAction(
                    kind="MANUAL_REVIEW",
                    property_id=property_id,
                    listing_id=None,
                    reason="Property is shared with live listings outside the remediation scope",
                    details={
                        "address": group[0].prop.address.normalized_address,
                        "source_keys": sorted({record.source_key for record in group}),
                        "source_item_ids": [record.listing.source_item_id for record in group],
                        "scoped_listing_count": len(scoped_listing_ids),
                        "all_live_listing_count": len(all_listing_ids),
                    },
                )
            )
            continue
        current = _property_identity(group[0].prop)
        identities = {record.identity for record in group}
        if len(group) == 1 or len(identities) == 1:
            intended = group[0].identity
            if current != intended:
                actions.append(
                    RepairAction(
                        kind="SYNC_PROPERTY",
                        property_id=property_id,
                        listing_id=group[0].listing.id if len(group) == 1 else None,
                        reason="Live source facts agree and differ from the property projection",
                        details={
                            "address": group[0].prop.address.normalized_address,
                            "source_keys": sorted({record.source_key for record in group}),
                            "source_item_ids": [record.listing.source_item_id for record in group],
                            "current": current.as_dict(),
                            "intended": intended.as_dict(),
                        },
                    )
                )
            continue

        known = [record for record in group if record.identity.unit_identifier]
        unknown = [record for record in group if not record.identity.unit_identifier]
        if len(group) == 2 and len(known) == 1 and len(unknown) == 1:
            movable = known[0]
            if _can_move_listing_evidence(session, movable):
                actions.append(
                    RepairAction(
                        kind="SPLIT_UNPROVEN_MERGE",
                        property_id=property_id,
                        listing_id=movable.listing.id,
                        reason="Only one source identifies a unit and its evidence is independent",
                        details={
                            "address": movable.prop.address.normalized_address,
                            "source_key": movable.source_key,
                            "moving_source_item_id": movable.listing.source_item_id,
                            "moving_identity": movable.identity.as_dict(),
                            "retained_source_item_id": unknown[0].listing.source_item_id,
                            "retained_identity": unknown[0].identity.as_dict(),
                        },
                    )
                )
                continue
        actions.append(
            RepairAction(
                kind="MANUAL_REVIEW",
                property_id=property_id,
                listing_id=None,
                reason=(
                    "Conflicting live source identities cannot be split safely by the narrow rule"
                ),
                details={
                    "address": group[0].prop.address.normalized_address,
                    "source_keys": sorted({record.source_key for record in group}),
                    "source_item_ids": [record.listing.source_item_id for record in group],
                    "identities": [record.identity.as_dict() for record in group],
                },
            )
        )
    return actions


def remediate_property_provenance(
    session: Session,
    *,
    apply: bool = False,
    source_key: str | None = None,
    active_only: bool = False,
) -> RemediationResult:
    records = _load_records(
        session,
        source_key=source_key,
        active_only=active_only,
    )
    by_listing = {record.listing.id: record for record in records}
    listing_updates = sum(
        _listing_identity(record.listing) != record.identity for record in records
    )
    actions = _plan_actions(session, records)

    if apply:
        actionable_listing_ids: set[UUID] = set()
        for action in actions:
            if action.kind == "SYNC_PROPERTY":
                actionable_listing_ids.update(
                    record.listing.id
                    for record in records
                    if record.prop.id == action.property_id
                    and (action.listing_id is None or record.listing.id == action.listing_id)
                )
            elif action.kind == "SPLIT_UNPROVEN_MERGE" and action.listing_id is not None:
                actionable_listing_ids.add(action.listing_id)
        for listing_id in actionable_listing_ids:
            record = by_listing[listing_id]
            _set_listing_identity(record.listing, record.identity)
        for action in actions:
            if action.kind == "SYNC_PROPERTY":
                record = next(
                    record
                    for record in records
                    if record.prop.id == action.property_id
                    and (action.listing_id is None or record.listing.id == action.listing_id)
                )
                _set_property_identity(record.prop, record.identity)
            elif action.kind == "SPLIT_UNPROVEN_MERGE" and action.listing_id is not None:
                record = by_listing[action.listing_id]
                old_property = record.prop
                new_property = Property(
                    address_id=old_property.address_id,
                    property_type=old_property.property_type,
                    unit_identifier=record.identity.unit_identifier,
                    rooms=record.identity.rooms,
                    area_m2=record.identity.area_m2,
                    new_construction=record.identity.new_construction,
                )
                session.add(new_property)
                session.flush()
                event_ids = set(
                    session.scalars(
                        select(Event.id).where(
                            Event.raw_item_id == record.listing.raw_item_id,
                            Event.property_id == old_property.id,
                        )
                    )
                )
                signal_ids = set(
                    session.scalars(
                        select(SignalEvidence.signal_id).where(
                            SignalEvidence.event_id.in_(event_ids),
                            SignalEvidence.superseded_at.is_(None),
                        )
                    )
                )
                record.listing.property_id = new_property.id
                for event in session.scalars(select(Event).where(Event.id.in_(event_ids))):
                    event.property_id = new_property.id
                for signal in session.scalars(select(Signal).where(Signal.id.in_(signal_ids))):
                    signal.property_id = new_property.id
                remaining = [
                    item
                    for item in records
                    if item.prop.id == old_property.id and item.listing.id != record.listing.id
                ]
                if len(remaining) == 1:
                    _set_property_identity(old_property, remaining[0].identity)
        session.commit()

    return RemediationResult(
        mode="apply" if apply else "dry-run",
        listings_examined=len(records),
        listing_provenance_updates=listing_updates,
        actions=tuple(actions),
    )
