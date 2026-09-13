import asyncio
import copy
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from flyttsignal.ingestion.contracts import AddressEnrichmentTarget
from flyttsignal.integrations.sources.address_enrichment.lantmateriet import (
    ATTRIBUTION,
    LantmaterietAddressAdapter,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "address_enrichment"
    / "lantmateriet"
    / "uppsala-belagenhetsadress-v4.2.json"
)
TARGET_ID = UUID("22222222-3333-4444-8555-666666666666")
EXTERNAL_ID = "11111111-2222-4333-8444-555555555555"


def fixture_payload() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def fixture_envelope() -> dict[str, Any]:
    return {
        "data_mode": "fixture",
        "source_item_id": EXTERNAL_ID,
        "source_url": f"https://api-ver.lantmateriet.se/example/{EXTERNAL_ID}",
        "target_address_id": str(TARGET_ID),
        "query": {"address": "Testgatan 12", "municipality_code": "0380"},
        "payload": fixture_payload(),
    }


def target() -> AddressEnrichmentTarget:
    return AddressEnrichmentTarget(
        address_id=TARGET_ID,
        address="Testgatan 12",
        municipality_code="0380",
    )


def test_lantmateriet_fixture_normalizes_basinfo_and_register_unit() -> None:
    item = LantmaterietAddressAdapter(live_enabled=False).normalize(fixture_envelope())
    assert item.target_address_id == TARGET_ID
    assert str(item.external_address_id) == EXTERNAL_ID
    assert item.canonical_address == "Testgatan 12"
    assert item.normalized_address == "Testgatan 12"
    assert item.municipality_code == "0380"
    assert item.postal_code == "75320"
    assert item.postal_town == "Uppsala"
    assert item.source_srid == 3006
    assert item.attribution == ATTRIBUTION
    assert item.source_attributes["license"] == "CC BY 4.0"
    assert item.source_attributes["data_mode"] == "fixture"
    assert item.register_unit_reference is not None
    assert item.register_unit_reference.designation == "UPPSALA TEST 1:1"
    assert item.register_unit_reference.register_unit_type == "Fastighet"


def test_lantmateriet_rejects_invalid_berorkrets_data() -> None:
    envelope = fixture_envelope()
    envelope["payload"] = copy.deepcopy(envelope["payload"])
    reference = envelope["payload"]["features"][0]["properties"]["registerenhetsreferens"]
    reference["typ"] = "Person"
    with pytest.raises(ValueError, match="type is invalid"):
        LantmaterietAddressAdapter(live_enabled=False).normalize(envelope)

    reference["typ"] = "Fastighet"
    reference["owner_name"] = "must not be accepted"
    with pytest.raises(ValueError, match="unknown fields"):
        LantmaterietAddressAdapter(live_enabled=False).normalize(envelope)


def test_lantmateriet_rejects_schema_or_scope_drift() -> None:
    wrong_crs = fixture_envelope()
    wrong_crs["payload"] = copy.deepcopy(wrong_crs["payload"])
    wrong_crs["payload"]["crs"]["properties"]["name"] = "urn:ogc:def:crs:EPSG::4326"
    with pytest.raises(ValueError, match="EPSG:3006"):
        LantmaterietAddressAdapter(live_enabled=False).normalize(wrong_crs)

    wrong_city = fixture_envelope()
    wrong_city["payload"] = copy.deepcopy(wrong_city["payload"])
    municipality = wrong_city["payload"]["features"][0]["properties"]["adressomrade"]["kommundel"][
        "kommun"
    ]
    municipality["kommunkod"] = "0180"
    with pytest.raises(ValueError, match="outside Uppsala"):
        LantmaterietAddressAdapter(live_enabled=False).normalize(wrong_city)


def test_lantmateriet_live_kill_switch_defaults_closed() -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(LantmaterietAddressAdapter(live_enabled=False).fetch([target()]))


def test_lantmateriet_fetch_uses_oauth_exact_match_and_minimal_data() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "test-token"}, request=request)
        if request.url.path.endswith("/referens/fritext"):
            return httpx.Response(
                200,
                json=[
                    {
                        "objektidentitet": EXTERNAL_ID,
                        "adress": "Testgatan 12",
                        "adressComponents": {
                            "kommun": "Uppsala",
                            "kommundel": "Uppsala",
                            "adressomrade": "Testgatan",
                            "adressplatsnummer": "12",
                            "postnummer": 75320,
                            "postort": "Uppsala",
                        },
                    }
                ],
                request=request,
            )
        if request.url.path.endswith(f"/{EXTERNAL_ID}"):
            return httpx.Response(200, json=fixture_payload(), request=request)
        return httpx.Response(404, request=request)

    async def run() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = LantmaterietAddressAdapter(
                client=client,
                live_enabled=True,
                client_id="client-id",
                client_secret="client-secret",
                max_retries=0,
            )
            return await adapter.fetch([target()])

    snapshots = asyncio.run(run())
    assert len(snapshots) == 1
    assert snapshots[0]["source_item_id"] == EXTERNAL_ID
    assert snapshots[0]["data_mode"] == "live"
    assert len(requests) == 3
    reference_request = requests[1]
    assert reference_request.url.params["kommunkod"] == "0380"
    assert reference_request.url.params["maxHits"] == "5"
    assert reference_request.url.params["status"] == "Gällande"
    detail_request = requests[2]
    assert detail_request.url.params["includeData"] == "basinformation,berorkrets"
    assert detail_request.url.params["srid"] == "3006"
    assert detail_request.headers["authorization"] == "Bearer test-token"


def test_lantmateriet_ambiguous_reference_fails_closed() -> None:
    reference = {
        "objektidentitet": EXTERNAL_ID,
        "adress": "Testgatan 12",
        "adressComponents": {
            "kommun": "Uppsala",
            "kommundel": "Uppsala",
            "adressomrade": "Testgatan",
            "adressplatsnummer": "12",
        },
    }
    assert LantmaterietAddressAdapter._select_exact_reference([reference], target()) == reference
    assert (
        LantmaterietAddressAdapter._select_exact_reference(
            [reference, copy.deepcopy(reference)], target()
        )
        is None
    )
