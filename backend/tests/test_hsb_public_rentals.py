import json
from pathlib import Path

import pytest

from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus, assess_snapshot
from flyttsignal.integrations.sources.rental_listings.hsb import (
    HSBPublicUppsalaAdapter,
    _deadline,
    _normalize_hsb,
    hsb_snapshot_evidence,
    parse_uppsala_search,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "rental_listings"
    / "hsb"
    / "uppsala-public-listings.json"
)


def test_hsb_fixture_preserves_direct_provenance() -> None:
    payloads = json.loads(FIXTURE.read_text(encoding="utf-8"))
    listing = _normalize_hsb(payloads[2], expected_mode="fixture")

    assert len(payloads) == 3
    assert listing.source_item_id == "1845-falhagen-236/50"
    assert listing.publisher_name == "HSB"
    assert listing.upstream_provider_key == "hsb-uppsala"
    assert listing.application_deadline.isoformat() == "2026-09-03"


def test_hsb_fixture_fails_closed_on_live_or_wrong_provider() -> None:
    base = {
        "source_item_id": "property/1",
        "address": "Testgatan 1",
        "city": "Uppsala",
        "publisher_name": "HSB",
        "upstream_provider_key": "hsb-uppsala",
        "upstream_provider_name": "HSB Uppsala",
    }
    with pytest.raises(ValueError, match="expected fixture"):
        _normalize_hsb({**base, "data_mode": "live"}, expected_mode="fixture")
    with pytest.raises(ValueError, match="HSB Uppsala provenance"):
        _normalize_hsb(
            {**base, "data_mode": "fixture", "upstream_provider_key": "homeq"},
            expected_mode="fixture",
        )


def test_hsb_partial_channel_cannot_emit_removal_events() -> None:
    assert not hasattr(HSBPublicUppsalaAdapter, "snapshot_complete")


def test_hsb_live_parser_filters_city_and_maps_public_card() -> None:
    html = """
    <div class="apartment-block">
      <div class="apartment-block__banner"><span>Tillsvidarekontrakt</span></div>
      <div class="apartment-block__showtimes">Sista anmälningsdag: 2026-09-03</div>
      <div class="apartment-block__details">
        <a href="/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/1845-falhagen-236/50/">
          <h4>Torkelsgatan 11</h4>
        </a>
        <div class="apartment-block__details-location">Uppsala, Fålhagen</div>
        <div>1 rok | 36,0 kvm | Vån 2 | Hyra 7 078 kr</div>
        <div class="apartment-block__details-movedate">Inflytt: 2026-12-01</div>
      </div>
    </div>
    <div class="apartment-block">
      <div class="apartment-block__details">
        <a href="/sok-bostad/sok-hyresratter/uppsala/enkoping/fastigheter/x/1/">
          <h4>Annan gata 1</h4>
        </a>
        <div class="apartment-block__details-location">Enköping, Centrum</div>
        <div>1 rok | 30 kvm | Hyra 5 000 kr</div>
      </div>
    </div>
    """

    items = parse_uppsala_search(html, max_items=10)

    assert items == [
        {
            "source_item_id": "1845-falhagen-236/50",
            "source_url": "https://www.hsb.se/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/1845-falhagen-236/50/",
            "address": "Torkelsgatan 11",
            "city": "Uppsala",
            "municipality_code": "0380",
            "rooms": "1",
            "area_m2": "36.0",
            "monthly_rent": "7078",
            "available_from": "2026-12-01",
            "application_deadline": "2026-09-03",
            "property_type": "rental",
            "publisher_name": "HSB",
            "upstream_provider_key": "hsb-uppsala",
            "upstream_provider_name": "HSB Uppsala",
            "categories": [
                "hyresrätt",
                "direktkanal",
                "publik-sökning",
                "Tillsvidarekontrakt",
            ],
            "data_mode": "live",
            "attribution": "Källa: HSB",
        }
    ]


def test_hsb_deadline_relative_labels_are_explicit() -> None:
    from datetime import date

    assert _deadline("I dag", today=date(2026, 8, 28)) == "2026-08-28"
    assert _deadline("I morgon", today=date(2026, 8, 28)) == "2026-08-29"


def test_hsb_exact_municipality_scope_can_be_complete() -> None:
    html = """
    <div class="apartment-block"><div class="apartment-block__details">
      <a href="/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/a/1/"><h4>A 1</h4></a>
      <div class="apartment-block__details-location">Uppsala, Centrum</div>
      <div>1 rok | 30 kvm | Hyra 5 000 kr</div>
    </div></div>
    <div class="apartment-block"><div class="apartment-block__details">
      <a href="/sok-bostad/sok-hyresratter/uppsala/enkoping/fastigheter/b/2/"><h4>B 2</h4></a>
      <div class="apartment-block__details-location">Enköping, Centrum</div>
      <div>1 rok | 30 kvm | Hyra 5 000 kr</div>
    </div></div>
    <a class="property-grid-card"
       href="/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/a/">
      1 ledig lägenhet
    </a>
    <a class="property-grid-card"
       href="/sok-bostad/sok-hyresratter/uppsala/enkoping/fastigheter/b/">
      1 ledig lägenhet
    </a>
    """
    items = parse_uppsala_search(html, max_items=10)
    evidence = hsb_snapshot_evidence(html, items, max_items=10)

    assert assess_snapshot(evidence).status is SnapshotStatus.COMPLETE
    assert evidence.items_reported == 1
    assert evidence.items_received == 1
    assert evidence.evidence["county_items_reported"] == 2
    assert evidence.evidence["county_items_received"] == 2


def test_hsb_count_mismatch_is_incomplete() -> None:
    html = """
    <div class="apartment-block"><div class="apartment-block__details">
      <a href="/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/a/1/"><h4>A 1</h4></a>
      <div class="apartment-block__details-location">Uppsala, Centrum</div>
      <div>1 rok | 30 kvm | Hyra 5 000 kr</div>
    </div></div>
    <a class="property-grid-card"
       href="/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/a/">
      2 lediga lägenheter
    </a>
    """
    items = parse_uppsala_search(html, max_items=10)
    evidence = hsb_snapshot_evidence(html, items, max_items=10)

    assert assess_snapshot(evidence).status is SnapshotStatus.INCOMPLETE
    assert "county_listing_count_mismatch" in evidence.reasons


def test_hsb_verified_empty_scope_is_allowed() -> None:
    html = """
    <a class="property-grid-card"
       href="/sok-bostad/sok-hyresratter/uppsala/uppsala/fastigheter/a/">
      0 lediga lägenheter
    </a>
    """
    items = parse_uppsala_search(html, max_items=10)
    evidence = hsb_snapshot_evidence(html, items, max_items=10)

    assert items == []
    assert assess_snapshot(evidence).status is SnapshotStatus.COMPLETE
