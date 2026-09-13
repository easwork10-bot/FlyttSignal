import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from flyttsignal.benchmarking.service import BenchmarkObservationInput
from flyttsignal.config import get_settings
from flyttsignal.ingestion.contracts import BenchmarkAdapter

TABLE_ID = "TAB6640"
MUNICIPALITY_CODE = "0380"
EXPECTED_DIMENSIONS = ["Region", "Alder", "Kon", "ContentsCode", "Tid"]
EXPECTED_METRICS = (
    "0000086B",
    "0000086F",
    "00000869",
    "00000867",
    "00000868",
    "0000086A",
    "0000086D",
    "0000086E",
    "0000086C",
)
DATA_PARAMS = {
    "lang": "sv",
    "valueCodes[Region]": MUNICIPALITY_CODE,
    "valueCodes[Alder]": "TOT1",
    "valueCodes[Kon]": "TotSa",
    "valueCodes[ContentsCode]": "*",
    "valueCodes[Tid]": "top(1)",
    "outputFormat": "json-stat2",
}
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class SCBMigrationAdapter(BenchmarkAdapter):
    source_key = "scb_pxweb_migration"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        live_enabled: bool | None = None,
        max_response_bytes: int = 1_000_000,
        max_retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._live_enabled = settings.scb_live_enabled if live_enabled is None else live_enabled
        self._base_url = settings.scb_api_base_url.rstrip("/")
        self._user_agent = settings.scb_user_agent
        self._max_response_bytes = max_response_bytes
        self._max_retries = max_retries
        self._sleep = sleep

    @property
    def data_url(self) -> str:
        return f"{self._base_url}/tables/{TABLE_ID}/data"

    async def fetch(self) -> list[dict[str, Any]]:
        if not self._live_enabled:
            raise RuntimeError(
                "SCB live collection is disabled; set SCB_LIVE_ENABLED=true after review"
            )
        if self._client is not None:
            payload, source_url = await self._request(self._client)
        else:
            timeout = httpx.Timeout(10.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                payload, source_url = await self._request(client)
        observations = self._normalize_payload(payload)
        period = observations[0].period
        return [
            {
                "source_item_id": f"{TABLE_ID}:{MUNICIPALITY_CODE}:{period}:total",
                "source_url": source_url,
                "payload": payload,
            }
        ]

    async def _request(self, client: httpx.AsyncClient) -> tuple[dict[str, Any], str]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with client.stream(
                    "GET",
                    self.data_url,
                    params=DATA_PARAMS,
                    headers={"Accept": "application/json", "User-Agent": self._user_agent},
                ) as response:
                    if response.status_code in RETRYABLE_STATUSES:
                        await response.aread()
                        if attempt < self._max_retries:
                            await self._sleep(self._retry_delay(response, attempt))
                            continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "application/json" not in content_type.lower():
                        raise ValueError(f"SCB returned unsupported content type: {content_type}")
                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > self._max_response_bytes:
                        raise ValueError("SCB response exceeds configured size limit")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_response_bytes:
                            raise ValueError("SCB response exceeds configured size limit")
                    payload = json.loads(body)
                    if not isinstance(payload, dict):
                        raise ValueError("SCB response must be a JSON object")
                    return payload, str(response.request.url)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await self._sleep(0.5 * (2**attempt))
                    continue
                raise
        raise RuntimeError("SCB request exhausted retries") from last_error

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                pass
        return 0.5 * (2**attempt)

    def normalize(self, item: dict[str, Any]) -> list[BenchmarkObservationInput]:
        payload = item.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("SCB raw item is missing its JSON payload")
        return self._normalize_payload(payload)

    def _normalize_payload(self, payload: dict[str, Any]) -> list[BenchmarkObservationInput]:
        if payload.get("version") != "2.0" or payload.get("class") != "dataset":
            raise ValueError("Unexpected SCB JSON-stat version or class")
        if payload.get("source") != "SCB":
            raise ValueError("Unexpected SCB dataset source")
        if payload.get("id") != EXPECTED_DIMENSIONS or payload.get("size") != [1, 1, 1, 9, 1]:
            raise ValueError("SCB TAB6640 schema drift detected")

        extension = payload.get("extension", {}).get("px", {})
        if extension.get("tableid") != TABLE_ID or extension.get("copyright") is not False:
            raise ValueError("Unexpected SCB table identity or copyright metadata")

        dimensions = payload.get("dimension")
        if not isinstance(dimensions, dict):
            raise ValueError("SCB response is missing dimensions")
        region = self._ordered_codes(dimensions, "Region")
        age = self._ordered_codes(dimensions, "Alder")
        gender = self._ordered_codes(dimensions, "Kon")
        metrics = self._ordered_codes(dimensions, "ContentsCode")
        periods = self._ordered_codes(dimensions, "Tid")
        if region != [MUNICIPALITY_CODE] or age != ["TOT1"] or gender != ["TotSa"]:
            raise ValueError("SCB response selection does not match the approved Uppsala totals")
        if tuple(metrics) != EXPECTED_METRICS or len(periods) != 1:
            raise ValueError("SCB metric or period schema drift detected")
        period = periods[0]
        if len(period) != 4 or not period.isdigit():
            raise ValueError("SCB period must be a four-digit year")

        values = payload.get("value")
        if not isinstance(values, list) or len(values) != len(EXPECTED_METRICS):
            raise ValueError("SCB response value count does not match its dimensions")
        metric_category = dimensions["ContentsCode"].get("category", {})
        labels = metric_category.get("label", {})
        units = metric_category.get("unit", {})
        if not isinstance(labels, dict) or not isinstance(units, dict):
            raise ValueError("SCB metric labels or units are missing")

        source_updated_at = self._parse_updated(payload.get("updated"))
        result = []
        for metric_code, raw_value in zip(metrics, values, strict=True):
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, type(None))):
                raise ValueError(f"SCB metric {metric_code} has a non-numeric value")
            unit = units.get(metric_code, {}).get("base")
            label = labels.get(metric_code)
            if not isinstance(unit, str) or not isinstance(label, str):
                raise ValueError(f"SCB metric {metric_code} metadata is incomplete")
            result.append(
                BenchmarkObservationInput(
                    dataset_key=TABLE_ID,
                    metric_key=metric_code,
                    municipality_code=MUNICIPALITY_CODE,
                    period=period,
                    value=Decimal(str(raw_value)) if raw_value is not None else None,
                    unit=unit,
                    dimensions={
                        "region": MUNICIPALITY_CODE,
                        "age": "TOT1",
                        "gender": "TotSa",
                        "metric_label": label,
                    },
                    source_updated_at=source_updated_at,
                )
            )
        return result

    @staticmethod
    def _ordered_codes(dimensions: dict[str, Any], name: str) -> list[str]:
        dimension = dimensions.get(name)
        if not isinstance(dimension, dict):
            raise ValueError(f"SCB response is missing dimension {name}")
        index = dimension.get("category", {}).get("index")
        if not isinstance(index, dict) or not all(
            isinstance(code, str) and isinstance(position, int) for code, position in index.items()
        ):
            raise ValueError(f"SCB dimension {name} has an invalid category index")
        positions = sorted(index.values())
        if positions != list(range(len(index))):
            raise ValueError(f"SCB dimension {name} category positions are not contiguous")
        return [code for code, _ in sorted(index.items(), key=lambda item: item[1])]

    @staticmethod
    def _parse_updated(value: Any) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("SCB updated timestamp must be a string")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
