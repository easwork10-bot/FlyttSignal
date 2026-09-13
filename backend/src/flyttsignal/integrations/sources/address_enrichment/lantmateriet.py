import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx

from flyttsignal.config import get_settings
from flyttsignal.enrichment.service import (
    AddressEnrichmentInput,
    RegisterUnitReferenceInput,
)
from flyttsignal.ingestion.contracts import AddressEnrichmentAdapter, AddressEnrichmentTarget
from flyttsignal.normalization.service import normalize_address

MUNICIPALITY_CODE = "0380"
SOURCE_SRID = 3006
MAX_REFERENCE_HITS = 5
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
ATTRIBUTION = "Belägenhetsadress Direkt © Lantmäteriet, CC BY 4.0; processed by FlyttSignal"


class LantmaterietAddressAdapter(AddressEnrichmentAdapter):
    source_key = "lantmateriet_belagenhetsadress"
    target_limit = 25

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        live_enabled: bool | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        max_response_bytes: int = 1_000_000,
        max_retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._live_enabled = (
            settings.lantmateriet_live_enabled if live_enabled is None else live_enabled
        )
        self._base_url = settings.lantmateriet_api_base_url.rstrip("/")
        self._token_url = settings.lantmateriet_token_url
        self._client_id = client_id if client_id is not None else settings.lantmateriet_client_id
        self._client_secret = (
            client_secret if client_secret is not None else settings.lantmateriet_client_secret
        )
        self._user_agent = settings.lantmateriet_user_agent
        self._max_response_bytes = max_response_bytes
        self._max_retries = max_retries
        self._sleep = sleep

    async def fetch(self, targets: list[AddressEnrichmentTarget]) -> list[dict[str, Any]]:
        if not self._live_enabled:
            raise RuntimeError(
                "Lantmäteriet live collection is disabled; configure credentials "
                "and enable it deliberately"
            )
        if not self._client_id or not self._client_secret:
            raise RuntimeError("Lantmäteriet OAuth client credentials are not configured")
        if len(targets) > self.target_limit:
            raise ValueError(f"Lantmäteriet target batch exceeds {self.target_limit}")
        if any(target.municipality_code != MUNICIPALITY_CODE for target in targets):
            raise ValueError("Lantmäteriet MVP only accepts Uppsala municipality 0380")

        if self._client is not None:
            return await self._fetch_with_client(self._client, targets)
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await self._fetch_with_client(client, targets)

    async def _fetch_with_client(
        self, client: httpx.AsyncClient, targets: list[AddressEnrichmentTarget]
    ) -> list[dict[str, Any]]:
        token_payload = await self._request_json(
            client,
            "POST",
            self._token_url,
            data={"grant_type": "client_credentials"},
            auth=httpx.BasicAuth(self._client_id or "", self._client_secret or ""),
            headers={"Accept": "application/json", "User-Agent": self._user_agent},
        )
        token = token_payload.get("access_token") if isinstance(token_payload, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError("Lantmäteriet OAuth response is missing access_token")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": self._user_agent,
        }

        snapshots: list[dict[str, Any]] = []
        for target in targets:
            references = await self._request_json(
                client,
                "GET",
                f"{self._base_url}/referens/fritext",
                params={
                    "adress": target.address,
                    "kommunkod": target.municipality_code,
                    "status": "Gällande",
                    "maxHits": MAX_REFERENCE_HITS,
                    "splitAdress": "true",
                },
                headers=headers,
            )
            reference = self._select_exact_reference(references, target)
            if reference is None:
                continue
            external_id = str(UUID(str(reference["objektidentitet"])))
            detail_url = f"{self._base_url}/{external_id}"
            payload = await self._request_json(
                client,
                "GET",
                detail_url,
                params={
                    "includeData": "basinformation,berorkrets",
                    "srid": SOURCE_SRID,
                },
                headers=headers,
            )
            snapshots.append(
                {
                    "data_mode": "live",
                    "source_item_id": external_id,
                    "source_url": detail_url,
                    "target_address_id": str(target.address_id),
                    "query": {
                        "address": target.address,
                        "municipality_code": target.municipality_code,
                    },
                    "payload": payload,
                }
            )
        return snapshots

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with client.stream(method, url, **kwargs) as response:
                    if response.status_code in RETRYABLE_STATUSES:
                        await response.aread()
                        if attempt < self._max_retries:
                            await self._sleep(self._retry_delay(response, attempt))
                            continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "application/json" not in content_type.lower():
                        raise ValueError(
                            f"Lantmäteriet returned unsupported content type: {content_type}"
                        )
                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > self._max_response_bytes:
                        raise ValueError("Lantmäteriet response exceeds configured size limit")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_response_bytes:
                            raise ValueError("Lantmäteriet response exceeds configured size limit")
                    return json.loads(body)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await self._sleep(0.5 * (2**attempt))
                    continue
                raise
        raise RuntimeError("Lantmäteriet request exhausted retries") from last_error

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                pass
        return 0.5 * (2**attempt)

    @classmethod
    def _select_exact_reference(
        cls, payload: Any, target: AddressEnrichmentTarget
    ) -> dict[str, Any] | None:
        if not isinstance(payload, list):
            raise ValueError("Lantmäteriet reference response must be a JSON array")
        matches = []
        for reference in payload:
            if not isinstance(reference, dict):
                raise ValueError("Lantmäteriet reference item must be an object")
            components = reference.get("adressComponents")
            if not isinstance(components, dict):
                continue
            candidate = cls._reference_address(components)
            municipality = str(components.get("kommun", "")).strip()
            if (
                candidate
                and normalize_address(candidate) == normalize_address(target.address)
                and municipality.casefold() == "uppsala"
            ):
                matches.append(reference)
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _reference_address(components: dict[str, Any]) -> str:
        area = str(
            components.get("gardsadressomrade") or components.get("adressomrade") or ""
        ).strip()
        number = str(components.get("adressplatsnummer") or "").strip()
        letter = str(components.get("bokstavstillagg") or "").strip()
        designation = f"{number}{letter}"
        return " ".join(part for part in (area, designation) if part)

    def normalize(self, item: dict[str, Any]) -> AddressEnrichmentInput:
        payload = item.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            raise ValueError("Lantmäteriet payload must be a GeoJSON FeatureCollection")
        crs_name = payload.get("crs", {}).get("properties", {}).get("name")
        if crs_name != "urn:ogc:def:crs:EPSG::3006":
            raise ValueError("Lantmäteriet response must use EPSG:3006")
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("Lantmäteriet detail response must contain exactly one feature")
        feature = features[0]
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("Lantmäteriet feature is malformed")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("Lantmäteriet feature properties are missing")
        register_unit_reference = self._parse_register_unit_reference(
            properties.get("registerenhetsreferens")
        )

        external_id = UUID(str(properties.get("objektidentitet")))
        if str(feature.get("id")) != str(external_id) or str(item.get("source_item_id")) != str(
            external_id
        ):
            raise ValueError("Lantmäteriet object identity is inconsistent")
        attributes = properties.get("adressplatsattribut")
        area = properties.get("adressomrade")
        if not isinstance(attributes, dict) or not isinstance(area, dict):
            raise ValueError("Lantmäteriet basinformation fields are incomplete")
        designation = attributes.get("adressplatsbeteckning")
        municipality = area.get("kommundel", {}).get("kommun", {})
        if not isinstance(designation, dict) or not isinstance(municipality, dict):
            raise ValueError("Lantmäteriet address designation or municipality is missing")
        municipality_code = str(municipality.get("kommunkod", ""))
        if municipality_code != MUNICIPALITY_CODE:
            raise ValueError("Lantmäteriet response is outside Uppsala municipality 0380")

        area_name = str(area.get("faststalltNamn", "")).strip()
        number = str(designation.get("adressplatsnummer", "")).strip()
        letter = str(designation.get("bokstavstillagg", "")).strip()
        canonical_address = " ".join(part for part in (area_name, f"{number}{letter}") if part)
        if not area_name or not number:
            raise ValueError("Lantmäteriet canonical address is incomplete")
        geometry = feature.get("geometry")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in coordinates
            )
        ):
            raise ValueError("Lantmäteriet point geometry is invalid")
        postal_code_value = attributes.get("postnummer")
        postal_code = str(postal_code_value) if postal_code_value is not None else None
        if postal_code is not None and (len(postal_code) != 5 or not postal_code.isdigit()):
            raise ValueError("Lantmäteriet postal code must contain five digits")
        status = str(attributes.get("statusForBelagenhetsadress", ""))
        if status != "Gällande" or attributes.get("objektstatus") != "Gällande":
            raise ValueError("Lantmäteriet address must be current")
        data_mode = str(item.get("data_mode", "fixture"))
        if data_mode not in {"fixture", "live"}:
            raise ValueError("Lantmäteriet data mode is invalid")

        return AddressEnrichmentInput(
            target_address_id=UUID(str(item.get("target_address_id"))),
            external_address_id=external_id,
            canonical_address=canonical_address,
            normalized_address=normalize_address(canonical_address),
            municipality_code=municipality_code,
            postal_code=postal_code,
            postal_town=str(attributes.get("postort", "")).strip() or None,
            status=status,
            source_srid=SOURCE_SRID,
            source_easting=coordinates[0],
            source_northing=coordinates[1],
            attribution=ATTRIBUTION,
            source_attributes={
                "object_version": attributes.get("objektversion"),
                "address_type": attributes.get("adressplatstyp"),
                "collection_location": attributes.get("insamlingslage"),
                "license": "CC BY 4.0",
                "processed": True,
                "data_mode": data_mode,
            },
            register_unit_reference=register_unit_reference,
        )

    @staticmethod
    def _parse_register_unit_reference(
        value: Any,
    ) -> RegisterUnitReferenceInput | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("Lantmäteriet register-unit reference must be an object")
        allowed_fields = {"objektidentitet", "beteckning", "typ"}
        if set(value) - allowed_fields:
            raise ValueError("Lantmäteriet register-unit reference contains unknown fields")
        designation = str(value.get("beteckning", "")).strip()
        register_unit_type = str(value.get("typ", "")).strip()
        if not designation:
            raise ValueError("Lantmäteriet register-unit designation is missing")
        if register_unit_type not in {"Fastighet", "Samfällighet"}:
            raise ValueError("Lantmäteriet register-unit type is invalid")
        return RegisterUnitReferenceInput(
            external_register_unit_id=UUID(str(value.get("objektidentitet"))),
            designation=designation,
            register_unit_type=register_unit_type,
        )
