import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from flyttsignal.config import get_settings
from flyttsignal.ingestion.contracts import SpatialFeatureAdapter
from flyttsignal.spatial.service import SpatialFeatureInput

DATASET_KEY = "uppsala_buildings"
MUNICIPALITY_CODE = "0380"
ATTRIBUTION = "Uppsala kommun, Öppna data"
LIVE_FILTER = "STYPE = 1001 AND ACTIVITYTYPE IN (0,1,3,5)"
OUT_FIELDS = "OBJECTID,STYPE,STATUS,ORIGINPLAN,MODIFICATIONDATE,ACTIVITYTYPE"
EXPECTED_FIELDS = set(OUT_FIELDS.split(","))
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

BUILDING_TYPES = {
    1001: "Bostad",
    1002: "Industri",
    1003: "Samhällsfunktion",
    1004: "Samfund",
    1005: "Verksamhet",
    1006: "Övrig byggnad",
    1007: "Ekonomibyggnad",
    1008: "Komplementbyggnad",
}
BUILDING_STATUSES = {
    0: "Ingen information",
    1: "Planerat",
    2: "Under uppförande",
    3: "Befintligt",
    4: "Rivet",
    5: "Raserat",
    6: "Till LINA",
}
BUILDING_ACTIVITIES = {
    0: "Godkänt bygglov",
    1: "Ny färdigbyggd byggnad",
    2: "Befintlig byggnad",
    3: "Byggnaden färdigbyggd",
    4: "Ändrad byggnadsinformation",
    5: "Riven eller nedbrunnen byggnad",
    6: "Felregistrerad byggnad",
}


class UppsalaBuildingsAdapter(SpatialFeatureAdapter):
    source_key = "uppsala_open_data_buildings"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        live_enabled: bool | None = None,
        page_size: int = 100,
        max_features: int | None = None,
        max_response_bytes: int = 5_000_000,
        max_retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._live_enabled = (
            settings.uppsala_open_data_live_enabled if live_enabled is None else live_enabled
        )
        self._layer_url = settings.uppsala_open_data_api_base_url.rstrip("/")
        self._user_agent = settings.uppsala_open_data_user_agent
        configured_max = settings.uppsala_open_data_max_features
        self._max_features = configured_max if max_features is None else max_features
        if not 1 <= page_size <= 1_000:
            raise ValueError("Uppsala Open Data page size must be between 1 and 1000")
        if not 1 <= self._max_features <= 1_000:
            raise ValueError("Uppsala Open Data bounded run must contain 1 to 1000 features")
        self._page_size = min(page_size, self._max_features)
        self._max_response_bytes = max_response_bytes
        self._max_retries = max_retries
        self._sleep = sleep

    async def fetch(self) -> list[dict[str, Any]]:
        if not self._live_enabled:
            raise RuntimeError(
                "Uppsala Open Data live collection is disabled; enable it deliberately "
                "after fixture verification"
            )
        if self._client is not None:
            return await self._fetch_with_client(self._client)
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            return await self._fetch_with_client(client)

    async def _fetch_with_client(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        offset = 0
        seen_ids: set[str] = set()
        while len(snapshots) < self._max_features:
            requested = min(self._page_size, self._max_features - len(snapshots))
            payload = await self._request_geojson(
                client,
                params={
                    "where": LIVE_FILTER,
                    "outFields": OUT_FIELDS,
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "orderByFields": "OBJECTID ASC",
                    "resultOffset": str(offset),
                    "resultRecordCount": str(requested),
                    "f": "geojson",
                },
            )
            features = payload.get("features")
            if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
                raise ValueError("Uppsala Open Data response must be a GeoJSON FeatureCollection")
            if len(features) > requested:
                raise ValueError("Uppsala Open Data returned more features than requested")
            for feature in features:
                if not isinstance(feature, dict):
                    raise ValueError("Uppsala Open Data feature must be an object")
                properties = feature.get("properties")
                if not isinstance(properties, dict):
                    raise ValueError("Uppsala Open Data feature properties are missing")
                source_item_id = str(properties.get("OBJECTID", ""))
                if not source_item_id or source_item_id in seen_ids:
                    raise ValueError("Uppsala Open Data returned a missing or duplicate OBJECTID")
                seen_ids.add(source_item_id)
                snapshots.append(
                    {
                        "data_mode": "live",
                        "dataset_key": DATASET_KEY,
                        "municipality_code": MUNICIPALITY_CODE,
                        "source_item_id": source_item_id,
                        "source_url": (
                            f"{self._layer_url}/query?where=OBJECTID%3D{source_item_id}"
                        ),
                        "payload": feature,
                    }
                )
            if len(features) < requested:
                break
            offset += len(features)
        return snapshots

    async def _request_geojson(
        self, client: httpx.AsyncClient, *, params: dict[str, str]
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with client.stream(
                    "GET",
                    f"{self._layer_url}/query",
                    params=params,
                    headers={
                        "Accept": "application/geo+json, application/json",
                        "User-Agent": self._user_agent,
                    },
                ) as response:
                    if response.status_code in RETRYABLE_STATUSES:
                        await response.aread()
                        if attempt < self._max_retries:
                            await self._sleep(self._retry_delay(response, attempt))
                            continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "json" not in content_type:
                        raise ValueError(
                            f"Uppsala Open Data returned unsupported content type: {content_type}"
                        )
                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > self._max_response_bytes:
                        raise ValueError("Uppsala Open Data response exceeds configured size limit")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_response_bytes:
                            raise ValueError(
                                "Uppsala Open Data response exceeds configured size limit"
                            )
                    payload = json.loads(body)
                    if not isinstance(payload, dict):
                        raise ValueError("Uppsala Open Data response must be a JSON object")
                    return payload
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await self._sleep(0.5 * (2**attempt))
                    continue
                raise
        raise RuntimeError("Uppsala Open Data request exhausted retries") from last_error

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                pass
        return 0.5 * (2**attempt)

    def normalize(self, item: dict[str, Any]) -> SpatialFeatureInput:
        if item.get("dataset_key") != DATASET_KEY:
            raise ValueError("Uppsala Open Data dataset identity is invalid")
        if item.get("municipality_code") != MUNICIPALITY_CODE:
            raise ValueError("Uppsala Open Data feature is outside Uppsala municipality 0380")
        feature = item.get("payload")
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("Uppsala Open Data payload must be a GeoJSON Feature")
        properties = feature.get("properties")
        if not isinstance(properties, dict) or set(properties) != EXPECTED_FIELDS:
            raise ValueError("Uppsala Open Data building schema drift detected")

        object_id = self._required_int(properties, "OBJECTID")
        if object_id <= 0 or str(object_id) != str(item.get("source_item_id")):
            raise ValueError("Uppsala Open Data OBJECTID is inconsistent")
        feature_id = feature.get("id")
        if feature_id is not None and str(feature_id) != str(object_id):
            raise ValueError("Uppsala Open Data GeoJSON feature id is inconsistent")

        subtype_code = self._required_int(properties, "STYPE")
        status_code = self._required_int(properties, "STATUS")
        activity_value = properties.get("ACTIVITYTYPE")
        if isinstance(activity_value, bool) or not isinstance(activity_value, (int, type(None))):
            raise ValueError("Uppsala Open Data ACTIVITYTYPE must be an integer or null")
        if subtype_code not in BUILDING_TYPES:
            raise ValueError("Uppsala Open Data contains an unknown building type")
        if status_code not in BUILDING_STATUSES:
            raise ValueError("Uppsala Open Data contains an unknown building status")
        if activity_value is not None and activity_value not in BUILDING_ACTIVITIES:
            raise ValueError("Uppsala Open Data contains an unknown building activity")
        origin_plan = properties.get("ORIGINPLAN")
        if isinstance(origin_plan, bool) or not isinstance(origin_plan, (int, type(None))):
            raise ValueError("Uppsala Open Data ORIGINPLAN must be an integer or null")

        modified_value = properties.get("MODIFICATIONDATE")
        if isinstance(modified_value, bool) or not isinstance(modified_value, (int, type(None))):
            raise ValueError("Uppsala Open Data modification timestamp is invalid")
        source_modified_at = (
            datetime.fromtimestamp(modified_value / 1000, tz=UTC)
            if modified_value is not None
            else None
        )
        if source_modified_at is not None and not 2000 <= source_modified_at.year <= 2100:
            raise ValueError("Uppsala Open Data modification timestamp is outside safe bounds")

        geometry = feature.get("geometry")
        geometry_wkt = self._geometry_wkt(geometry)
        data_mode = str(item.get("data_mode", "fixture"))
        if data_mode not in {"fixture", "live"}:
            raise ValueError("Uppsala Open Data data mode is invalid")

        return SpatialFeatureInput(
            dataset_key=DATASET_KEY,
            source_item_id=str(object_id),
            municipality_code=MUNICIPALITY_CODE,
            feature_type="building",
            subtype_code=subtype_code,
            subtype_label=BUILDING_TYPES[subtype_code],
            status_code=status_code,
            status_label=BUILDING_STATUSES[status_code],
            activity_code=activity_value,
            activity_label=(
                BUILDING_ACTIVITIES[activity_value] if activity_value is not None else None
            ),
            source_modified_at=source_modified_at,
            geometry_wkt=geometry_wkt,
            geometry_geojson=geometry,
            attribution=ATTRIBUTION,
            source_attributes={
                "origin_plan": origin_plan,
                "license_basis": "Uppsala municipality open-data policy",
                "score_neutral": True,
            },
            data_mode=data_mode,
        )

    @staticmethod
    def _required_int(properties: dict[str, Any], field: str) -> int:
        value = properties.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Uppsala Open Data {field} must be an integer")
        return value

    @classmethod
    def _geometry_wkt(cls, geometry: Any) -> str:
        if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
            raise ValueError("Uppsala Open Data geometry schema is invalid")
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon":
            return f"POLYGON{cls._polygon_wkt(coordinates)}"
        if geometry_type == "MultiPolygon" and isinstance(coordinates, list) and coordinates:
            polygons = ",".join(cls._polygon_wkt(polygon) for polygon in coordinates)
            return f"MULTIPOLYGON({polygons})"
        raise ValueError("Uppsala Open Data geometry must be Polygon or MultiPolygon")

    @classmethod
    def _polygon_wkt(cls, polygon: Any) -> str:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Uppsala Open Data polygon must contain rings")
        return f"({','.join(cls._ring_wkt(ring) for ring in polygon)})"

    @classmethod
    def _ring_wkt(cls, ring: Any) -> str:
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("Uppsala Open Data polygon ring is too short")
        points = [cls._point(point) for point in ring]
        if points[0] != points[-1]:
            raise ValueError("Uppsala Open Data polygon ring is not closed")
        return f"({','.join(f'{cls._number(x)} {cls._number(y)}' for x, y in points)})"

    @staticmethod
    def _point(point: Any) -> tuple[float, float]:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) for value in point
            )
        ):
            raise ValueError("Uppsala Open Data polygon coordinate is invalid")
        longitude, latitude = float(point[0]), float(point[1])
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("Uppsala Open Data geometry is not WGS84")
        return longitude, latitude

    @staticmethod
    def _number(value: float) -> str:
        return format(value, ".15g")
