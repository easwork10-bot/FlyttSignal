import json
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from flyttsignal.config import get_settings
from flyttsignal.domains.developments.models import RentalDevelopment
from flyttsignal.ingestion.contracts import RentalDevelopmentAdapter
from flyttsignal.integrations.sources.homeq import (
    homeq_provider_key,
    parse_homeq_search_response,
)


def parse_project_page(html: str, search_result: dict[str, Any]) -> dict[str, Any]:
    script = HTMLParser(html).css_first("script#__NEXT_DATA__")
    if script is None:
        raise ValueError("HomeQ project bootstrap data not found")
    try:
        project = json.loads(script.text())["props"]["pageProps"]["project"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("HomeQ project schema not found") from exc
    if not isinstance(project, dict):
        raise ValueError("HomeQ project must be an object")
    location = project.get("project_location")
    landlord = project.get("landlord")
    ranges = project.get("range_information")
    if (
        not isinstance(location, dict)
        or not isinstance(landlord, dict)
        or not isinstance(ranges, dict)
    ):
        raise ValueError("HomeQ project is missing location, landlord or ranges")
    project_id = str(project.get("id") or "").strip()
    provider_name = str(landlord.get("name") or "").strip()
    street = str(location.get("street") or "").strip()
    street_number = str(location.get("street_number") or "").strip()
    if not project_id or not provider_name or not street or location.get("city") != "Uppsala":
        raise ValueError("HomeQ project is missing identity or is outside Uppsala")

    def bounds(name: str) -> tuple[Any, Any]:
        value = ranges.get(name)
        if not isinstance(value, list) or len(value) != 2:
            return None, None
        return value[0], value[1]

    rent_min, rent_max = bounds("rent")
    rooms_min, rooms_max = bounds("rooms")
    area_min, area_max = bounds("area")
    return {
        "source_item_id": project_id,
        "source_url": urljoin("https://www.homeq.se", str(search_result.get("uri") or "")),
        "name": str(project.get("name") or "").strip(),
        "upstream_provider_key": homeq_provider_key(provider_name, landlord.get("id")),
        "upstream_provider_name": provider_name,
        "address": " ".join(part for part in (street, street_number) if part),
        "city": "Uppsala",
        "municipality_code": "0380",
        "planned_unit_count": project.get("apartment_count"),
        "active_listing_count": int(search_result.get("active_ads") or 0),
        "rent_min": rent_min,
        "rent_max": rent_max,
        "rooms_min": rooms_min,
        "rooms_max": rooms_max,
        "area_min": area_min,
        "area_max": area_max,
        "available_from": project.get("preliminary_move_in_date"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "status": "ACTIVE" if project.get("published") and not project.get("closed") else "CLOSED",
        "data_mode": "live",
        "attribution": f"Källa: HomeQ; projektuppgifter från {provider_name}",
    }


class HomeQPublicUppsalaProjectAdapter(RentalDevelopmentAdapter):
    """Public project cards stored separately from their real apartment ads."""

    source_key = "homeq_public_uppsala_projects"

    async def fetch(self) -> list[dict[str, Any]]:
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
            response = await client.post(
                settings.homeq_public_search_api_url,
                json={
                    "geo_bounds": bounds,
                    "zoom": settings.homeq_uppsala_zoom,
                    "page": 1,
                    "amount": settings.homeq_public_max_items,
                },
            )
            response.raise_for_status()
            results, _ = parse_homeq_search_response(
                response.json(), max_items=settings.homeq_public_max_items
            )
            cards = [
                item
                for item in results
                if item.get("type") == "project"
                and item.get("municipality") == "Uppsala"
                and item.get("city") == "Uppsala"
            ]
            parsed: list[dict[str, Any]] = []
            for card in cards:
                path = str(card.get("uri") or "")
                if not path.startswith("/projekt/"):
                    raise ValueError("HomeQ project result has an invalid detail path")
                detail = await client.get(urljoin("https://www.homeq.se", path))
                detail.raise_for_status()
                parsed.append(parse_project_page(detail.text, card))
            return parsed

    def normalize(self, item: dict[str, Any]) -> RentalDevelopment:
        return RentalDevelopment.model_validate(item)
