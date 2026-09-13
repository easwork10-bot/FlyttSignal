import asyncio
import json
import math
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from flyttsignal.config import get_settings
from flyttsignal.ingestion.contracts import (
    FetchResult,
    SnapshotEvidence,
    SourceAdapter,
)
from flyttsignal.integrations.sources.homeq import (
    homeq_provider_key,
    parse_homeq_search_response,
)
from flyttsignal.normalization.service import NormalizedItem, normalize_item


def homeq_snapshot_evidence(
    *,
    request_count: int,
    search_page_count: int,
    base_card_count: int,
    ordinary_listing_count: int,
    project_count: int,
    project_listing_count: int,
    items_received: int,
    hit_result_limit: bool,
    bounds: dict[str, float],
) -> SnapshotEvidence:
    """Describe completeness for the exact configured public search, not all of HomeQ."""

    items_reported = ordinary_listing_count + project_listing_count
    return SnapshotEvidence(
        requests_attempted=request_count,
        requests_succeeded=request_count,
        requests_failed=0,
        pages_expected=search_page_count,
        pages_received=search_page_count,
        items_reported=items_reported,
        items_received=items_received,
        pagination_complete=True,
        hit_result_limit=hit_result_limit,
        inventory_scope_complete=True,
        rule_version="homeq-public-search-v2",
        reasons=("configured_search_scope_fully_paginated",),
        evidence={
            "transport": "json_search_and_html_detail",
            "scope": "configured_uppsala_geo_bounds",
            "geo_bounds": bounds,
            "base_card_count": base_card_count,
            "ordinary_listings_reported": ordinary_listing_count,
            "project_cards_expanded": project_count,
            "project_listings_reported": project_listing_count,
        },
    )


def parse_detail_page(html: str, search_result: dict[str, Any]) -> dict[str, Any]:
    script = HTMLParser(html).css_first("script#__NEXT_DATA__")
    if script is None:
        raise ValueError("HomeQ detail bootstrap data not found")
    try:
        detail = json.loads(script.text())["props"]["pageProps"]["objectAd"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("HomeQ detail schema not found") from exc
    if not isinstance(detail, dict):
        raise ValueError("HomeQ objectAd must be an object")

    source_item_id = str(search_result.get("id") or "").strip()
    path = str(search_result.get("uri") or "").strip()
    provider_name = str(detail.get("landlord_company") or "").strip()
    provider = detail.get("landlord")
    provider_id = provider.get("id") if isinstance(provider, dict) else None
    street = str(detail.get("street") or "").strip()
    street_number = str(detail.get("street_number") or "").strip()
    if not source_item_id or not path or not provider_name or not street or not street_number:
        raise ValueError("HomeQ listing is missing identity, address or landlord")
    if detail.get("municipality") != "Uppsala" or detail.get("city") != "Uppsala":
        raise ValueError("HomeQ detail result is outside Uppsala")

    return {
        "source_item_id": source_item_id,
        "source_url": urljoin("https://www.homeq.se", path),
        "address": f"{street} {street_number}",
        "city": "Uppsala",
        "municipality_code": "0380",
        "rooms": detail.get("rooms"),
        "area_m2": detail.get("area"),
        "monthly_rent": detail.get("rent"),
        "available_from": detail.get("date_access"),
        "listed_at": detail.get("date_publish"),
        "latitude": detail.get("latitude"),
        "longitude": detail.get("longitude"),
        "property_type": "rental",
        "new_construction": bool(detail.get("new_production")),
        "unit_identifier": detail.get("landlord_object_id"),
        "project_source_item_id": (
            str(detail["project_id"]) if detail.get("project_id") is not None else None
        ),
        "publisher_name": "HomeQ",
        "upstream_provider_key": homeq_provider_key(provider_name, provider_id),
        "upstream_provider_name": provider_name,
        "categories": [
            "hyresrätt",
            "marknadsplats",
            "publik-sökning",
            *(["projektbostad"] if detail.get("project_id") is not None else []),
        ],
        "data_mode": "live",
        "attribution": f"Källa: HomeQ; annonsuppgifter från {provider_name}",
    }


def _normalize_homeq(item: dict[str, Any], *, expected_mode: str) -> NormalizedItem:
    normalized = normalize_item(item)
    if normalized.data_mode != expected_mode:
        raise ValueError(f"HomeQ adapter expected {expected_mode} data")
    if normalized.publisher_name != "HomeQ":
        raise ValueError("HomeQ listing must preserve HomeQ as publisher")
    if not normalized.upstream_provider_key or not normalized.upstream_provider_name:
        raise ValueError("HomeQ listings require their upstream landlord")
    return normalized


class HomeQPublicUppsalaAdapter(SourceAdapter):
    """Bounded anonymous search plus public detail-page facts."""

    source_key = "homeq_public_uppsala_live_rentals"

    async def fetch(self) -> FetchResult[dict[str, Any]]:
        settings = get_settings()
        if not settings.homeq_public_live_enabled:
            raise ValueError("HomeQ live collection is disabled by configuration")
        headers = {
            "User-Agent": settings.homeq_public_user_agent,
            "Accept": "application/json, text/html;q=0.9",
        }
        bounds = {
            "min_lat": settings.homeq_uppsala_min_lat,
            "max_lat": settings.homeq_uppsala_max_lat,
            "min_lng": settings.homeq_uppsala_min_lng,
            "max_lng": settings.homeq_uppsala_max_lng,
        }
        async with httpx.AsyncClient(
            timeout=settings.homeq_public_timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:

            async def search_page(page: int) -> dict[str, Any]:
                response = await client.post(
                    settings.homeq_public_search_api_url,
                    json={
                        "geo_bounds": bounds,
                        "zoom": settings.homeq_uppsala_zoom,
                        "page": page,
                        "amount": settings.homeq_public_page_size,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("HomeQ search response must be an object")
                return payload

            first_payload = await search_page(1)
            first_results, total_hits = parse_homeq_search_response(
                first_payload, max_items=settings.homeq_public_max_items
            )
            page_count = math.ceil(total_hits / settings.homeq_public_page_size)
            remaining = await asyncio.gather(
                *(search_page(page) for page in range(2, page_count + 1))
            )
            results = list(first_results)
            for payload in remaining:
                page_results, page_total = parse_homeq_search_response(
                    payload, max_items=settings.homeq_public_max_items
                )
                if page_total != total_hits:
                    raise ValueError("HomeQ result count changed during pagination")
                results.extend(page_results)
            if len(results) != total_hits:
                raise ValueError("HomeQ paginated result count does not match total_hits")

            def in_uppsala(result: dict[str, Any]) -> bool:
                address = result.get("address")
                nested_city = address.get("city") if isinstance(address, dict) else None
                nested_municipality = (
                    address.get("municipality") if isinstance(address, dict) else None
                )
                return (result.get("municipality") or nested_municipality) == "Uppsala" and (
                    result.get("city") or nested_city
                ) == "Uppsala"

            ordinary_listing_count = sum(
                result.get("type") == "individual" and in_uppsala(result) for result in results
            )
            projects = [
                result
                for result in results
                if result.get("type") == "project" and in_uppsala(result)
            ]
            project_hit_limit = False
            project_listing_count = 0
            for project in projects:
                project_id = project.get("id")
                if not isinstance(project_id, int):
                    raise ValueError("HomeQ project result has no stable numeric identifier")
                project_payload = await search_page_for_project(client, project_id, settings)
                project_results, project_total = parse_homeq_search_response(
                    project_payload,
                    max_items=settings.homeq_public_max_items,
                    allow_empty=True,
                )
                if project_total != int(project.get("active_ads") or 0):
                    raise ValueError("HomeQ project active-ad count changed during collection")
                if len(project_results) != project_total:
                    raise ValueError("HomeQ project result count does not match total_hits")
                project_listing_count += project_total
                project_hit_limit = project_hit_limit or (
                    project_total >= settings.homeq_public_max_items
                )
                results.extend(project_results)

            individuals_by_id = {
                str(result.get("id")): result
                for result in results
                if result.get("type") == "individual" and in_uppsala(result)
            }
            individuals = list(individuals_by_id.values())
            items_reported = ordinary_listing_count + project_listing_count
            if not individuals:
                raise ValueError("HomeQ returned no individual Uppsala listings")
            if len(individuals) != items_reported:
                raise ValueError(
                    "HomeQ unique Uppsala listings do not match reported ordinary and project ads"
                )
            if len(individuals) > settings.homeq_public_max_items:
                raise ValueError("HomeQ expanded inventory exceeds configured bounds")

            semaphore = asyncio.Semaphore(settings.homeq_public_concurrency)

            async def fetch_detail(result: dict[str, Any]) -> dict[str, Any]:
                path = str(result.get("uri") or "")
                if not path.startswith("/lagenhet/"):
                    raise ValueError("HomeQ individual result has an invalid detail path")
                async with semaphore:
                    response = await client.get(urljoin("https://www.homeq.se", path))
                response.raise_for_status()
                return parse_detail_page(response.text, result)

            details = list(await asyncio.gather(*(fetch_detail(item) for item in individuals)))
            request_count = page_count + len(projects) + len(individuals)
            search_page_count = page_count + len(projects)
            return FetchResult(
                details,
                homeq_snapshot_evidence(
                    request_count=request_count,
                    search_page_count=search_page_count,
                    base_card_count=total_hits,
                    ordinary_listing_count=ordinary_listing_count,
                    project_count=len(projects),
                    project_listing_count=project_listing_count,
                    items_received=len(details),
                    hit_result_limit=(
                        total_hits >= settings.homeq_public_max_items
                        or len(individuals) >= settings.homeq_public_max_items
                        or project_hit_limit
                    ),
                    bounds=bounds,
                ),
            )

    def normalize(self, item: dict[str, Any]) -> NormalizedItem:
        return _normalize_homeq(item, expected_mode="live")


async def search_page_for_project(
    client: httpx.AsyncClient, project_id: int, settings: Any
) -> dict[str, Any]:
    response = await client.post(
        settings.homeq_public_search_api_url,
        json={"project": project_id, "page": 1, "amount": settings.homeq_public_max_items},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("HomeQ project search response must be an object")
    return payload
