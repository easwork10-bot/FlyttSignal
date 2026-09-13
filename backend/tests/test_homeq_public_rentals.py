import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from flyttsignal.domains.developments.models import RentalDevelopment
from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus, assess_snapshot
from flyttsignal.integrations.sources.homeq import (
    parse_homeq_search_response as parse_search_response,
)
from flyttsignal.integrations.sources.rental_developments.homeq import (
    HomeQPublicUppsalaProjectAdapter,
    parse_project_page,
)
from flyttsignal.integrations.sources.rental_listings.homeq import (
    HomeQPublicUppsalaAdapter,
    _normalize_homeq,
    homeq_snapshot_evidence,
    parse_detail_page,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "rental_listings"
    / "homeq"
    / "uppsala-public-listings.json"
)


def test_homeq_fixture_preserves_publisher_and_upstream_provider() -> None:
    payloads = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first = _normalize_homeq(payloads[0], expected_mode="fixture")
    assert len(payloads) == 3
    assert first.source_item_id == "276824"
    assert first.publisher_name == "HomeQ"
    assert first.upstream_provider_key == "lansa"
    assert first.monthly_rent == 12092
    assert first.listed_at.isoformat() == "2026-08-27"


def test_homeq_fixture_fails_closed_on_live_or_missing_provider() -> None:
    base = {
        "source_item_id": "1",
        "address": "Testgatan 1",
        "city": "Uppsala",
        "publisher_name": "HomeQ",
        "upstream_provider_key": "test",
        "upstream_provider_name": "Test",
    }
    with pytest.raises(ValueError, match="expected fixture"):
        _normalize_homeq({**base, "data_mode": "live"}, expected_mode="fixture")
    with pytest.raises(ValueError, match="upstream landlord"):
        _normalize_homeq(
            {**base, "data_mode": "fixture", "upstream_provider_key": None},
            expected_mode="fixture",
        )


def test_homeq_public_sample_cannot_emit_removal_events() -> None:
    assert not hasattr(HomeQPublicUppsalaAdapter, "snapshot_complete")


def test_homeq_search_and_detail_parsers_keep_only_normalized_public_facts() -> None:
    result = {
        "id": 277037,
        "type": "individual",
        "uri": "/lagenhet/277037-4rum-uppsala-uppsala-lan-valthornsvagen-65",
        "municipality": "Uppsala",
        "city": "Uppsala",
    }
    results, count = parse_search_response({"results": [result], "total_hits": 1}, max_items=10)
    detail = {
        "street": "Valthornsvägen",
        "street_number": "65",
        "municipality": "Uppsala",
        "city": "Uppsala",
        "rooms": "4.0",
        "area": "83.00",
        "rent": 15020,
        "date_access": "2026-10-01",
        "date_publish": "2026-08-28",
        "latitude": "59.8120700",
        "longitude": "17.6320710",
        "new_production": False,
        "landlord_company": "Oppeby Fastighets AB",
        "landlord": {"id": 2252},
        "landlord_object_id": "A-1201",
        "project_id": 1053,
        "description": "Must not be retained",
        "images": [{"image": "must-not-be-retained.jpg"}],
    }
    bootstrap = {"props": {"pageProps": {"objectAd": detail}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(bootstrap)}</script>'

    item = parse_detail_page(html, results[0])

    assert count == 1
    assert item["source_item_id"] == "277037"
    assert item["address"] == "Valthornsvägen 65"
    assert item["upstream_provider_key"] == "homeq-landlord-2252"
    assert item["unit_identifier"] == "A-1201"
    assert item["project_source_item_id"] == "1053"
    assert "projektbostad" in item["categories"]
    assert "description" not in item
    assert "images" not in item


def test_homeq_live_adapter_requires_explicit_switch(monkeypatch) -> None:
    monkeypatch.setattr(
        "flyttsignal.integrations.sources.rental_listings.homeq.get_settings",
        lambda: SimpleNamespace(homeq_public_live_enabled=False),
    )
    with pytest.raises(ValueError, match="disabled by configuration"):
        asyncio.run(HomeQPublicUppsalaAdapter().fetch())


def test_homeq_search_parser_fails_closed_on_schema_and_volume() -> None:
    with pytest.raises(ValueError, match="schema"):
        parse_search_response({}, max_items=10)
    with pytest.raises(ValueError, match="configured bounds"):
        parse_search_response({"results": [], "total_hits": 11}, max_items=10)


def test_homeq_complete_status_is_limited_to_the_configured_search_scope() -> None:
    snapshot = homeq_snapshot_evidence(
        request_count=58,
        search_page_count=5,
        base_card_count=26,
        ordinary_listing_count=24,
        project_count=2,
        project_listing_count=29,
        items_received=53,
        hit_result_limit=False,
        bounds={"min_lat": 59.77, "max_lat": 59.91, "min_lng": 17.45, "max_lng": 17.83},
    )
    assessment = assess_snapshot(snapshot)

    assert assessment.status is SnapshotStatus.COMPLETE
    assert assessment.rule_version == "homeq-public-search-v2"
    assert snapshot.items_reported == 53
    assert snapshot.evidence["scope"] == "configured_uppsala_geo_bounds"


def test_homeq_reported_count_mismatch_cannot_be_complete() -> None:
    snapshot = homeq_snapshot_evidence(
        request_count=58,
        search_page_count=5,
        base_card_count=26,
        ordinary_listing_count=24,
        project_count=2,
        project_listing_count=29,
        items_received=52,
        hit_result_limit=False,
        bounds={"min_lat": 59.77, "max_lat": 59.91, "min_lng": 17.45, "max_lng": 17.83},
    )

    assert assess_snapshot(snapshot).status is SnapshotStatus.INCOMPLETE


def test_homeq_project_parser_keeps_project_separate_from_listing() -> None:
    card = {
        "id": 1053,
        "uri": "/projekt/1053",
        "active_ads": 29,
    }
    project = {
        "id": 1053,
        "name": "Klacken",
        "published": True,
        "closed": False,
        "apartment_count": 193,
        "preliminary_move_in_date": "2026-12-01",
        "range_information": {
            "rent": [7429, 9226],
            "rooms": ["1.0", "1.0"],
            "area": ["24.00", "35.00"],
        },
        "landlord": {"id": 1028, "name": "Klövern"},
        "project_location": {
            "latitude": "59.8709202",
            "longitude": "17.6656656",
            "street": "Vaksalagatan",
            "street_number": "",
            "city": "Uppsala",
        },
        "info_description": "Must not be retained",
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps({'props': {'pageProps': {'project': project}}})}"
        "</script>"
    )

    item = parse_project_page(html, card)
    normalized = HomeQPublicUppsalaProjectAdapter().normalize(item)

    assert isinstance(normalized, RentalDevelopment)
    assert normalized.source_item_id == "1053"
    assert normalized.active_listing_count == 29
    assert normalized.planned_unit_count == 193
    assert normalized.upstream_provider_key == "klovern"
    assert "info_description" not in item

    invalid = normalized.model_dump()
    invalid["data_mode"] = "fixture"
    with pytest.raises(ValueError, match="must be live data"):
        RentalDevelopment.model_validate(invalid)
