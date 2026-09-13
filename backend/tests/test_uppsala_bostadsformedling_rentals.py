import asyncio
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from flyttsignal.ingestion.contracts import complete_fixture_result
from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus, assess_snapshot
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    AVAILABLE_RENTALS_QUERY,
    RENTAL_OBJECT_DETAIL_QUERY,
    UppsalaBostadsformedlingAdapter,
    _normalize_ubf_item,
    enrich_rental_objects,
    parse_available_rental_objects,
    parse_rental_object_detail,
    ubf_snapshot_evidence,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "rental_listings"
    / "uppsala_bostadsformedling"
    / "rentals.json"
)
DETAIL_CONTRACT = FIXTURE.with_name("detail-contract.json")


def _settings(*, live: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        uppsala_bostadsformedling_live_enabled=live,
        uppsala_bostadsformedling_max_items=500,
        uppsala_bostadsformedling_graphql_url="https://example.test/graphql",
        uppsala_bostadsformedling_detail_enabled=False,
        uppsala_bostadsformedling_detail_concurrency=2,
    )


def _graphql_object(**overrides) -> dict:
    return {
        "rentalObjectId": 200062438843,
        "street": "Sköldmövägen 19 C",
        "rooms": 1,
        "area": 36,
        "rent": 7140,
        "startDate": "2026-08-28T00:00:00",
        "endDate": "2026-08-31T23:59:00",
        "moveInDate": "2026-10-01T00:00:00",
        "landlord": "Rikshem",
        "landlordId": 123,
        "regionName": "Uppsala",
        "latitude": 59.88,
        "longitude": 17.65,
        "boendeTyp": [{"rentalObjectCategoryId": "YOUTH", "name": "Ungdom"}],
        "bostadsTyp": [{"rentalObjectCategoryId": "APARTMENT", "name": "Lägenhet"}],
        "kontraktsTyp": [{"rentalObjectCategoryId": "PERMANENT", "name": "Tillsvidarekontrakt"}],
        **overrides,
    }


def _payload(*objects: dict) -> dict:
    return {"data": {"getRentalObjectsAvailable": {"rentalObjects": list(objects)}}}


def test_ubf_fixture_preserves_publisher_and_provider_roles() -> None:
    fixture_result = complete_fixture_result(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    listings = [
        _normalize_ubf_item(item, expected_mode="fixture") for item in fixture_result
    ]

    assert len(listings) == 3
    assert {listing.upstream_provider_key for listing in listings} == {
        "newsec",
        "rikshem",
        "stena-fastigheter",
    }
    assert {listing.publisher_name for listing in listings} == {"Uppsala Bostadsförmedling"}
    assert listings[1].upstream_provider_name == "Newsec (förvaltning)"
    assert "fastighetsägare kan variera" in listings[1].attribution
    assert assess_snapshot(fixture_result.snapshot).status is SnapshotStatus.COMPLETE


def test_ubf_graphql_parser_maps_minimal_public_fields_and_filters_city() -> None:
    items = parse_available_rental_objects(
        _payload(
            _graphql_object(),
            _graphql_object(
                rentalObjectId=2,
                street="Annan väg 1",
                landlord="Ny värd",
                landlordId=456,
                regionName="Enköping",
            ),
        ),
        data_mode="live",
        max_items=10,
    )

    assert items == [
        {
            "source_item_id": "200062438843",
            "source_url": "https://www.bostad.uppsala.se/mypages/app/visa/200062438843",
            "address": "Sköldmövägen 19 C",
            "city": "Uppsala",
            "municipality_code": "0380",
            "rooms": 1,
            "area_m2": 36,
            "monthly_rent": 7140,
            "available_from": "2026-10-01",
            "application_deadline": "2026-08-31",
            "listed_at": "2026-08-28",
            "latitude": 59.88,
            "longitude": 17.65,
            "property_type": "rental",
            "publisher_name": "Uppsala Bostadsförmedling",
            "upstream_provider_key": "rikshem",
            "upstream_provider_name": "Rikshem",
            "categories": [
                "hyresrätt",
                "marknadsplats",
                "publik-graphql",
                "Ungdom",
                "Lägenhet",
                "Tillsvidarekontrakt",
            ],
            "data_mode": "live",
            "attribution": (
                "Källa: Uppsala Bostadsförmedling; publicerad hyresvärd/förvaltare: Rikshem"
            ),
        }
    ]


def test_ubf_unknown_provider_uses_stable_landlord_id() -> None:
    item = parse_available_rental_objects(
        _payload(_graphql_object(landlord="Ny värd", landlordId=456)),
        data_mode="live",
        max_items=10,
    )[0]
    assert item["upstream_provider_key"] == "ubf-landlord-456"


def test_ubf_parser_fails_closed_on_errors_schema_drift_and_volume() -> None:
    with pytest.raises(ValueError, match="contains errors"):
        parse_available_rental_objects(
            {"errors": [{"message": "failed"}]}, data_mode="live", max_items=10
        )
    with pytest.raises(ValueError, match="schema"):
        parse_available_rental_objects({}, data_mode="live", max_items=10)
    with pytest.raises(ValueError, match="configured cap"):
        parse_available_rental_objects(_payload(_graphql_object()), data_mode="live", max_items=0)


def test_ubf_live_has_no_static_completeness_switch(monkeypatch) -> None:
    settings = _settings(live=True)
    monkeypatch.setattr(
        "flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling.get_settings",
        lambda: settings,
    )
    assert not hasattr(UppsalaBostadsformedlingAdapter(), "snapshot_complete")


def test_ubf_adapter_requires_kill_switch(monkeypatch) -> None:
    settings = _settings(live=False)
    monkeypatch.setattr(
        "flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling.get_settings",
        lambda: settings,
    )
    adapter = UppsalaBostadsformedlingAdapter()

    assert adapter.source_key == "uppsala_bostadsformedling_live_rentals"
    with pytest.raises(ValueError, match="disabled by configuration"):
        asyncio.run(adapter.fetch())


def test_ubf_query_excludes_applicant_and_rich_content_fields() -> None:
    assert "applicationCount" not in AVAILABLE_RENTALS_QUERY
    assert "description" not in AVAILABLE_RENTALS_QUERY
    assert "image" not in AVAILABLE_RENTALS_QUERY.casefold()
    assert "criteria" not in AVAILABLE_RENTALS_QUERY.casefold()


def test_ubf_detail_contract_preserves_scoped_identity_and_positive_status() -> None:
    cases = json.loads(DETAIL_CONTRACT.read_text(encoding="utf-8"))["cases"]
    first = cases[0]

    detail = parse_rental_object_detail(
        first["response"],
        expected_source_item_id=first["requested_id"],
        expected_provider_key="klovern",
    )

    assert detail["unit_identifier"] == "C-1006"
    assert detail["landlord_object_number"] == "C-1006"
    assert detail["apartment_number"] == "1006"
    assert detail["new_construction"] is True
    assert detail["source_project_id"] == "200054150693"
    assert detail["source_project_name"] == "Klacken"
    assert detail["detail_evidence"]["status_codes"] == ["NEW-PRODUCTION"]


def test_ubf_empty_detail_status_is_unknown_not_false() -> None:
    case = json.loads(DETAIL_CONTRACT.read_text(encoding="utf-8"))["cases"][2]

    detail = parse_rental_object_detail(
        case["response"],
        expected_source_item_id=case["requested_id"],
        expected_provider_key="uppsalahem",
    )

    assert detail["unit_identifier"] == "7001-012-01-0346"
    assert detail["apartment_number"] == "1010"
    assert detail["new_construction"] is None
    assert detail["source_project_id"] is None


@pytest.mark.parametrize("status", [None, [{"rentalObjectCategoryId": "OTHER", "name": "Övrigt"}]])
def test_ubf_missing_null_and_unrecognized_detail_status_remain_unknown(status) -> None:
    case = json.loads(DETAIL_CONTRACT.read_text(encoding="utf-8"))["cases"][2]
    response = deepcopy(case["response"])
    if status is None:
        response["data"]["getRentalObject"].pop("fastighetsStatus")
    else:
        response["data"]["getRentalObject"]["fastighetsStatus"] = status

    detail = parse_rental_object_detail(
        response,
        expected_source_item_id=case["requested_id"],
        expected_provider_key="uppsalahem",
    )

    assert detail["new_construction"] is None


def test_ubf_malformed_detail_status_is_rejected() -> None:
    case = json.loads(DETAIL_CONTRACT.read_text(encoding="utf-8"))["cases"][2]
    response = deepcopy(case["response"])
    response["data"]["getRentalObject"]["fastighetsStatus"] = "NEW-PRODUCTION"

    with pytest.raises(ValueError, match="fastighetsStatus must be a list"):
        parse_rental_object_detail(
            response,
            expected_source_item_id=case["requested_id"],
            expected_provider_key="uppsalahem",
        )


@pytest.mark.parametrize("mismatch", ["listing", "provider"])
def test_ubf_detail_contract_rejects_identity_mismatches(mismatch: str) -> None:
    case = json.loads(DETAIL_CONTRACT.read_text(encoding="utf-8"))["cases"][1]
    source_item_id = "wrong" if mismatch == "listing" else case["requested_id"]
    provider_key = "wrong" if mismatch == "provider" else "ubf-landlord-100017249115"

    with pytest.raises(ValueError, match="does not match inventory"):
        parse_rental_object_detail(
            case["response"],
            expected_source_item_id=source_item_id,
            expected_provider_key=provider_key,
        )


def test_ubf_detail_query_stays_within_verified_non_personal_contract() -> None:
    assert "getRentalObject($rentalObjectId: Long!)" in RENTAL_OBJECT_DETAIL_QUERY
    assert "applicationCount" not in RENTAL_OBJECT_DETAIL_QUERY
    assert "description" not in RENTAL_OBJECT_DETAIL_QUERY
    assert "criteria" not in RENTAL_OBJECT_DETAIL_QUERY.casefold()


def test_ubf_bounded_detail_enrichment_retains_inventory_on_partial_failure(
    monkeypatch,
) -> None:
    cases = json.loads(DETAIL_CONTRACT.read_text(encoding="utf-8"))["cases"]
    settings = _settings(live=True)
    monkeypatch.setattr(
        "flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling.get_settings",
        lambda: settings,
    )
    items = [
        {
            "source_item_id": cases[0]["requested_id"],
            "upstream_provider_key": "klovern",
        },
        {
            "source_item_id": cases[1]["requested_id"],
            "upstream_provider_key": "ubf-landlord-100017249115",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["operationName"] == "getRentalObject"
        assert body["variables"].keys() == {"rentalObjectId"}
        if body["variables"]["rentalObjectId"] == int(cases[0]["requested_id"]):
            return httpx.Response(200, json=cases[0]["response"])
        return httpx.Response(503)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await enrich_rental_objects(client, items, concurrency=2)

    enriched, succeeded, failed = asyncio.run(run())

    assert (len(enriched), succeeded, failed) == (2, 1, 1)
    assert enriched[0]["new_construction"] is True
    assert enriched[0]["new_construction_observation_complete"] is True
    assert enriched[0]["detail_enrichment"]["status"] == "SUCCESS"
    assert enriched[1]["source_item_id"] == cases[1]["requested_id"]
    assert enriched[1]["new_construction"] is None
    assert enriched[1]["new_construction_observation_complete"] is False
    assert enriched[1]["detail_enrichment"] == {
        "status": "FAILED",
        "reason": "http_status_error",
    }


def test_ubf_detail_failure_blocks_lifecycle_without_erasing_inventory_completeness() -> None:
    payload = _payload(_graphql_object())
    items = parse_available_rental_objects(payload, data_mode="live", max_items=10)
    evidence = ubf_snapshot_evidence(
        payload,
        items,
        max_items=10,
        detail_attempted=1,
        detail_succeeded=0,
        detail_failed=1,
    )

    assert evidence.inventory_scope_complete is True
    assert evidence.items_reported == evidence.items_received == 1
    assert evidence.evidence["detail_enrichment"]["failed"] == 1
    assert assess_snapshot(evidence).status is SnapshotStatus.INCOMPLETE


def test_ubf_parameterless_inventory_can_be_complete() -> None:
    payload = _payload(
        _graphql_object(),
        _graphql_object(
            rentalObjectId=2,
            street="Annan väg 1",
            landlord="Ny värd",
            landlordId=456,
            regionName="Enköping",
        ),
    )
    items = parse_available_rental_objects(payload, data_mode="live", max_items=10)
    evidence = ubf_snapshot_evidence(payload, items, max_items=10)

    assert assess_snapshot(evidence).status is SnapshotStatus.COMPLETE
    assert evidence.items_reported == 1
    assert evidence.items_received == 1
    assert evidence.evidence["global_items_received"] == 2
    assert evidence.evidence["global_unique_identifiers"] == 2


def test_ubf_missing_region_is_incomplete() -> None:
    payload = _payload(
        _graphql_object(),
        _graphql_object(rentalObjectId=2, regionName=None),
    )
    items = parse_available_rental_objects(payload, data_mode="live", max_items=10)
    evidence = ubf_snapshot_evidence(payload, items, max_items=10)

    assert assess_snapshot(evidence).status is SnapshotStatus.INCOMPLETE
    assert "global_item_missing_region" in evidence.reasons


def test_ubf_global_duplicate_is_incomplete() -> None:
    payload = _payload(
        _graphql_object(),
        _graphql_object(
            street="Annan väg 1",
            landlord="Ny värd",
            landlordId=456,
            regionName="Enköping",
        ),
    )
    items = parse_available_rental_objects(payload, data_mode="live", max_items=10)
    evidence = ubf_snapshot_evidence(payload, items, max_items=10)

    assert assess_snapshot(evidence).status is SnapshotStatus.INCOMPLETE
    assert "global_duplicate_identifiers" in evidence.reasons
