from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from flyttsignal.domains.properties.identity import PropertyIdentity
from flyttsignal.property_provenance.service import ListingRecord, _plan_actions


class ListingIdSession:
    def __init__(self, listing_ids: list) -> None:
        self.listing_ids = listing_ids

    def scalars(self, _statement):
        return iter(self.listing_ids)


def record() -> ListingRecord:
    listing = SimpleNamespace(
        id=uuid4(),
        status="ACTIVE",
        source_item_id="source-unit-1",
    )
    prop = SimpleNamespace(
        id=uuid4(),
        unit_identifier=None,
        rooms=Decimal("2.0"),
        area_m2=Decimal("44.0"),
        new_construction=False,
        address=SimpleNamespace(normalized_address="Examplegatan 1"),
    )
    return ListingRecord(
        listing=listing,
        prop=prop,
        identity=PropertyIdentity(None, Decimal("2"), Decimal("44"), None),
        source_key="example_live_source",
    )


def test_sync_manifest_identifies_its_exact_source() -> None:
    item = record()
    actions = _plan_actions(ListingIdSession([item.listing.id]), [item])  # type: ignore[arg-type]

    assert len(actions) == 1
    assert actions[0].kind == "SYNC_PROPERTY"
    assert actions[0].details["source_keys"] == ["example_live_source"]


def test_source_scoped_repair_fails_closed_for_shared_property() -> None:
    item = record()
    actions = _plan_actions(  # type: ignore[arg-type]
        ListingIdSession([item.listing.id, uuid4()]),
        [item],
    )

    assert len(actions) == 1
    assert actions[0].kind == "MANUAL_REVIEW"
    assert actions[0].details["all_live_listing_count"] == 2
