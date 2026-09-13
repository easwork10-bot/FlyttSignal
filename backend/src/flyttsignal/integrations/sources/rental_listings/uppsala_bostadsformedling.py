import asyncio
from collections import Counter
from datetime import datetime
from typing import Any

import httpx

from flyttsignal.config import get_settings
from flyttsignal.domains.housing_providers.identity import canonical_provider_key
from flyttsignal.ingestion.contracts import (
    FetchResult,
    SnapshotEvidence,
    SourceAdapter,
)
from flyttsignal.normalization.service import NormalizedItem, normalize_item

AVAILABLE_RENTALS_QUERY = """
query getRentalObjectsAvailable {
  getRentalObjectsAvailable {
    rentalObjects {
      rentalObjectId
      street
      rooms
      area
      rent
      startDate
      endDate
      moveInDate
      landlord
      landlordId
      regionName
      latitude
      longitude
      boendeTyp { rentalObjectCategoryId name }
      bostadsTyp { rentalObjectCategoryId name }
      kontraktsTyp { rentalObjectCategoryId name }
    }
  }
}
"""

RENTAL_OBJECT_DETAIL_QUERY = """
query getRentalObject($rentalObjectId: Long!) {
  getRentalObject(rentalObjectId: $rentalObjectId) {
    rentalObjectId
    objectNumber
    apartmentNumber
    street
    rooms
    area
    projectId
    projectName
    fastighetsStatus { rentalObjectCategoryId name }
    landlord { landlordId name }
  }
}
"""


def _date(value: object) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"UBF returned an invalid date: {value}") from exc


def _provider_key(name: str, landlord_id: object) -> str:
    return canonical_provider_key(name, "ubf-landlord", landlord_id)


def _category_names(item: dict[str, Any]) -> list[str]:
    names = ["hyresrätt", "marknadsplats", "publik-graphql"]
    for field in ("boendeTyp", "bostadsTyp", "kontraktsTyp"):
        values = item.get(field)
        if values is None:
            continue
        if not isinstance(values, list):
            raise ValueError(f"UBF field {field} must be a list")
        names.extend(str(value["name"]).strip() for value in values if value.get("name"))
    return list(dict.fromkeys(names))


def _available_objects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("errors"):
        raise ValueError("UBF GraphQL response contains errors")
    try:
        objects = payload["data"]["getRentalObjectsAvailable"]["rentalObjects"]
    except (KeyError, TypeError) as exc:
        raise ValueError("UBF GraphQL rental-object schema not found") from exc
    if not isinstance(objects, list):
        raise ValueError("UBF rentalObjects must be a list")
    if not objects:
        raise ValueError("UBF response contained no rental objects")
    if not all(isinstance(item, dict) for item in objects):
        raise ValueError("UBF rental object must be an object")
    return objects


def parse_rental_object_detail(
    payload: dict[str, Any],
    *,
    expected_source_item_id: str,
    expected_provider_key: str,
) -> dict[str, Any]:
    """Validate one public detail response without inventing negative source facts."""

    if payload.get("errors"):
        raise ValueError("UBF detail GraphQL response contains errors")
    try:
        detail = payload["data"]["getRentalObject"]
    except (KeyError, TypeError) as exc:
        raise ValueError("UBF detail GraphQL schema not found") from exc
    if not isinstance(detail, dict):
        raise ValueError("UBF detail rental object must be an object")

    source_item_id = str(detail.get("rentalObjectId") or "").strip()
    if source_item_id != expected_source_item_id:
        raise ValueError("UBF detail rental-object identity does not match inventory")

    landlord = detail.get("landlord")
    if not isinstance(landlord, dict):
        raise ValueError("UBF detail landlord must be an object")
    provider_name = str(landlord.get("name") or "").strip()
    if not provider_name:
        raise ValueError("UBF detail landlord is missing its name")
    provider_key = _provider_key(provider_name, landlord.get("landlordId"))
    if provider_key != expected_provider_key:
        raise ValueError("UBF detail landlord does not match inventory")

    statuses = detail.get("fastighetsStatus")
    if statuses is None:
        status_items: list[dict[str, Any]] = []
    elif not isinstance(statuses, list) or not all(
        isinstance(status, dict) for status in statuses
    ):
        raise ValueError("UBF detail fastighetsStatus must be a list")
    else:
        status_items = statuses
    status_codes = [
        str(status.get("rentalObjectCategoryId") or "").strip()
        for status in status_items
        if status.get("rentalObjectCategoryId")
    ]
    status_names = [
        str(status.get("name") or "").strip()
        for status in status_items
        if status.get("name")
    ]

    object_number = str(detail.get("objectNumber") or "").strip() or None
    apartment_number = str(detail.get("apartmentNumber") or "").strip() or None
    project_id = detail.get("projectId")
    return {
        "unit_identifier": object_number,
        "landlord_object_number": object_number,
        "apartment_number": apartment_number,
        "new_construction": True if "NEW-PRODUCTION" in status_codes else None,
        "source_project_id": str(project_id) if project_id is not None else None,
        "source_project_name": str(detail.get("projectName") or "").strip() or None,
        "detail_evidence": {
            "status_codes": status_codes,
            "status_names": status_names,
            "provider_key": provider_key,
        },
    }


async def enrich_rental_objects(
    client: httpx.AsyncClient,
    items: list[dict[str, Any]],
    *,
    concurrency: int,
) -> tuple[list[dict[str, Any]], int, int]:
    """Enrich a bounded inventory without turning detail failures into missing listings."""

    if concurrency < 1:
        raise ValueError("UBF detail concurrency must be positive")
    semaphore = asyncio.Semaphore(concurrency)

    async def enrich(item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        try:
            rental_object_id = int(item["source_item_id"])
            async with semaphore:
                response = await client.post(
                    get_settings().uppsala_bostadsformedling_graphql_url,
                    json={
                        "query": RENTAL_OBJECT_DETAIL_QUERY,
                        "operationName": "getRentalObject",
                        "variables": {"rentalObjectId": rental_object_id},
                    },
                )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("UBF detail GraphQL response was not JSON") from exc
            detail = parse_rental_object_detail(
                payload,
                expected_source_item_id=item["source_item_id"],
                expected_provider_key=item["upstream_provider_key"],
            )
        except httpx.HTTPStatusError:
            failure_reason = "http_status_error"
        except httpx.HTTPError:
            failure_reason = "transport_error"
        except (KeyError, TypeError, ValueError):
            failure_reason = "contract_error"
        else:
            return {
                **item,
                **detail,
                "new_construction_observation_complete": True,
                "detail_enrichment": {
                    "status": "SUCCESS",
                    "operation": "getRentalObject",
                },
            }, True
        return {
            **item,
            "new_construction": None,
            "new_construction_observation_complete": False,
            "detail_enrichment": {
                "status": "FAILED",
                "reason": failure_reason,
            },
        }, False

    results = await asyncio.gather(*(enrich(item) for item in items))
    enriched = [item for item, _succeeded in results]
    succeeded = sum(succeeded for _item, succeeded in results)
    return enriched, succeeded, len(results) - succeeded


def parse_available_rental_objects(
    payload: dict[str, Any], *, data_mode: str, max_items: int
) -> list[dict[str, Any]]:
    objects = _available_objects(payload)

    items: list[dict[str, Any]] = []
    for raw in objects:
        if raw.get("regionName") != "Uppsala":
            continue
        source_item_id = str(raw.get("rentalObjectId") or "").strip()
        address = str(raw.get("street") or "").strip()
        provider_name = str(raw.get("landlord") or "").strip()
        if not source_item_id or not address or not provider_name:
            raise ValueError("UBF listing is missing identity, address or landlord")
        provider_key = _provider_key(provider_name, raw.get("landlordId"))
        items.append(
            {
                "source_item_id": source_item_id,
                "source_url": f"https://www.bostad.uppsala.se/mypages/app/visa/{source_item_id}",
                "address": address,
                "city": "Uppsala",
                "municipality_code": "0380",
                "rooms": raw.get("rooms"),
                "area_m2": raw.get("area"),
                "monthly_rent": raw.get("rent"),
                "available_from": _date(raw.get("moveInDate")),
                "application_deadline": _date(raw.get("endDate")),
                "listed_at": _date(raw.get("startDate")),
                "latitude": raw.get("latitude"),
                "longitude": raw.get("longitude"),
                "property_type": "rental",
                "publisher_name": "Uppsala Bostadsförmedling",
                "upstream_provider_key": provider_key,
                "upstream_provider_name": provider_name,
                "categories": _category_names(raw),
                "data_mode": data_mode,
                "attribution": (
                    "Källa: Uppsala Bostadsförmedling; "
                    f"publicerad hyresvärd/förvaltare: {provider_name}"
                ),
            }
        )
    if not items:
        raise ValueError("UBF response contained no Uppsala rental objects")
    if len(items) > max_items:
        raise ValueError(f"UBF Uppsala result exceeds configured cap ({max_items})")
    if len({item["source_item_id"] for item in items}) != len(items):
        raise ValueError("UBF response contains duplicate rental-object identifiers")
    return items


def ubf_snapshot_evidence(
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    max_items: int,
    detail_attempted: int = 0,
    detail_succeeded: int = 0,
    detail_failed: int = 0,
) -> SnapshotEvidence:
    objects = _available_objects(payload)
    identifiers = [str(item.get("rentalObjectId") or "").strip() for item in objects]
    regions = [str(item.get("regionName") or "").strip() for item in objects]
    uppsala_reported = sum(region == "Uppsala" for region in regions)

    reasons: list[str] = []
    if any(not identifier for identifier in identifiers):
        reasons.append("global_item_missing_identity")
    if len(set(identifiers)) != len(identifiers):
        reasons.append("global_duplicate_identifiers")
    if any(not region for region in regions):
        reasons.append("global_item_missing_region")
    if len(items) != uppsala_reported:
        reasons.append("uppsala_item_count_mismatch")
    scope_complete = not reasons
    if detail_failed:
        reasons.append("detail_enrichment_incomplete")
    if scope_complete:
        reasons.append("parameterless_public_inventory_matches_graphql_array")

    return SnapshotEvidence(
        requests_attempted=1 + detail_attempted,
        requests_succeeded=1 + detail_succeeded,
        requests_failed=detail_failed,
        pages_expected=1,
        pages_received=1,
        items_reported=uppsala_reported,
        items_received=len(items),
        pagination_complete=True,
        hit_result_limit=len(items) >= max_items,
        inventory_scope_complete=scope_complete,
        rule_version="ubf-public-graphql-v2",
        reasons=tuple(reasons),
        evidence={
            "transport": "graphql",
            "operation": "getRentalObjectsAvailable",
            "operation_variables": [],
            "scope_filter": "regionName=Uppsala",
            "global_items_received": len(objects),
            "global_unique_identifiers": len(set(identifiers)),
            "region_counts": dict(sorted(Counter(regions).items())),
            "detail_enrichment": {
                "attempted": detail_attempted,
                "succeeded": detail_succeeded,
                "failed": detail_failed,
            },
        },
    )


def _normalize_ubf_item(item: dict[str, Any], *, expected_mode: str) -> NormalizedItem:
    normalized = normalize_item(item)
    if normalized.publisher_name != "Uppsala Bostadsförmedling":
        raise ValueError("UBF listings must preserve the public publisher")
    if not normalized.upstream_provider_key or not normalized.upstream_provider_name:
        raise ValueError("UBF listings require their upstream housing provider")
    if normalized.data_mode != expected_mode:
        raise ValueError(f"UBF adapter expected {expected_mode} data")
    return normalized


class UppsalaBostadsformedlingAdapter(SourceAdapter):
    """Anonymous public GraphQL adapter protected by source and environment gates."""

    source_key = "uppsala_bostadsformedling_live_rentals"

    async def fetch(self) -> FetchResult[dict[str, Any]]:
        settings = get_settings()
        if not settings.uppsala_bostadsformedling_live_enabled:
            raise ValueError("UBF live collection is disabled by configuration")

        async with httpx.AsyncClient(
            timeout=settings.uppsala_bostadsformedling_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.uppsala_bostadsformedling_user_agent,
                "Accept": "application/graphql-response+json, application/json",
            },
        ) as client:
            response = await client.post(
                settings.uppsala_bostadsformedling_graphql_url,
                json={
                    "query": AVAILABLE_RENTALS_QUERY,
                    "operationName": "getRentalObjectsAvailable",
                },
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("UBF GraphQL response was not JSON") from exc
            items = parse_available_rental_objects(
                payload,
                data_mode="live",
                max_items=settings.uppsala_bostadsformedling_max_items,
            )
            detail_attempted = 0
            detail_succeeded = 0
            detail_failed = 0
            if settings.uppsala_bostadsformedling_detail_enabled:
                detail_attempted = len(items)
                items, detail_succeeded, detail_failed = await enrich_rental_objects(
                    client,
                    items,
                    concurrency=settings.uppsala_bostadsformedling_detail_concurrency,
                )
        return FetchResult(
            items,
            ubf_snapshot_evidence(
                payload,
                items,
                max_items=settings.uppsala_bostadsformedling_max_items,
                detail_attempted=detail_attempted,
                detail_succeeded=detail_succeeded,
                detail_failed=detail_failed,
            ),
        )

    def normalize(self, item: dict[str, Any]) -> NormalizedItem:
        return _normalize_ubf_item(item, expected_mode="live")
