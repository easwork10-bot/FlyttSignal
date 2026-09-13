import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from flyttsignal.integrations.sources.rental_listings.heimstaden import (
    HeimstadenUppsalaAdapter,
    parse_uppsala_page,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "rental_listings"
    / "heimstaden"
    / "uppsala-listings.html"
)


def test_heimstaden_fixture_parses_stable_public_fields() -> None:
    items = parse_uppsala_page(
        FIXTURE.read_text(encoding="utf-8"), data_mode="fixture", max_items=25
    )
    assert len(items) == 3
    assert items[0] == {
        "source_item_id": "1238103-1401",
        "source_url": "https://heimstaden.com/se/sok-lagenhet/Uppsala-71m²-1238103-1401",
        "address": "Kryddblandargatan 49",
        "city": "Uppsala",
        "municipality_code": "0380",
        "rooms": "3",
        "area_m2": "71",
        "monthly_rent": "14032",
        "available_from": "2026-12-01",
        "property_type": "rental",
        "publisher_name": "Heimstaden",
        "upstream_provider_key": "heimstaden",
        "upstream_provider_name": "Heimstaden",
        "categories": ["hyresrätt", "direktkanal"],
        "data_mode": "fixture",
        "attribution": "Källa: Heimstaden",
    }


def test_heimstaden_parser_fails_closed_on_schema_drift_and_volume() -> None:
    with pytest.raises(ValueError, match="schema"):
        parse_uppsala_page("<html></html>", data_mode="fixture", max_items=25)
    with pytest.raises(ValueError, match="cap"):
        parse_uppsala_page(FIXTURE.read_text(encoding="utf-8"), data_mode="fixture", max_items=2)


def test_heimstaden_landing_page_cannot_emit_removal_events() -> None:
    assert not hasattr(HeimstadenUppsalaAdapter, "snapshot_complete")


def test_explicit_empty_uppsala_search_is_valid():
    html = '<input name="text" value="Uppsala"><strong data-hose-total-nr-of-matches-nr>0</strong>'
    assert parse_uppsala_page(html, data_mode="fixture", max_items=25) == []
    with pytest.raises(ValueError, match="schema"):
        parse_uppsala_page(html.replace("Uppsala", "Stockholm"), data_mode="fixture", max_items=25)
    with pytest.raises(ValueError, match="schema"):
        parse_uppsala_page(html.replace(">0<", ">3<"), data_mode="fixture", max_items=25)


def test_empty_search_does_not_import_other_cities():
    html = '<input name="text" value="Uppsala"><strong data-hose-total-nr-of-matches-nr>0</strong>'
    html += FIXTURE.read_text(encoding="utf-8").replace("Uppsala - Uppsala", "Stockholm - Salem")
    assert parse_uppsala_page(html, data_mode="fixture", max_items=25) == []


def test_empty_count_contradiction_and_duplicate_ids_fail():
    html = FIXTURE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="contradicts"):
        parse_uppsala_page(
            '<input name="text" value="Uppsala"><strong data-hose-total-nr-of-matches-nr>0</strong>'
            + html,
            data_mode="fixture",
            max_items=25,
        )
    with pytest.raises(ValueError, match="duplicate"):
        parse_uppsala_page(html + html, data_mode="fixture", max_items=25)


def test_heimstaden_adapter_requires_explicit_switch(monkeypatch) -> None:
    monkeypatch.setattr(
        "flyttsignal.integrations.sources.rental_listings.heimstaden.get_settings",
        lambda: SimpleNamespace(heimstaden_live_enabled=False),
    )
    with pytest.raises(ValueError, match="disabled by configuration"):
        asyncio.run(HeimstadenUppsalaAdapter().fetch())
