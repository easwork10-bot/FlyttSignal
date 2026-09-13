import re
from datetime import date
from typing import Any

import httpx
from selectolax.parser import HTMLParser, Node

from flyttsignal.config import get_settings
from flyttsignal.ingestion.contracts import (
    FetchResult,
    SnapshotEvidence,
    SourceAdapter,
)
from flyttsignal.normalization.service import NormalizedItem, normalize_item

MONTHS = {
    "januari": 1,
    "februari": 2,
    "mars": 3,
    "april": 4,
    "maj": 5,
    "juni": 6,
    "juli": 7,
    "augusti": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


def _text(node: Node | None) -> str:
    return " ".join(node.text(strip=True).split()) if node else ""


def _number(value: str) -> str | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value.replace("\xa0", "").replace(" ", ""))
    return match.group(0).replace(",", ".") if match else None


def _swedish_date(value: str) -> str | None:
    match = re.search(r"(\d{1,2})\s+([a-zåäö]+),?\s+(\d{4})", value.lower())
    if not match or match.group(2) not in MONTHS:
        return None
    return date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1))).isoformat()


def parse_uppsala_page(html: str, *, data_mode: str, max_items: int) -> list[dict[str, Any]]:
    page = HTMLParser(html)
    cards = page.css(".object-card")
    search = page.css_first('input[name="text"]')
    count = page.css_first("[data-hose-total-nr-of-matches-nr]")
    explicit_empty = (
        search is not None
        and search.attributes.get("value", "").strip().casefold() == "uppsala"
        and _text(count) == "0"
    )
    if not cards:
        if explicit_empty:
            return []
        raise ValueError("Heimstaden listing-card schema not found")
    items: list[dict[str, Any]] = []
    for card in cards:
        location = _text(card.css_first(".object-card__location"))
        if not location.lower().startswith("uppsala -"):
            continue
        link = card.css_first("a[href*='/se/sok-lagenhet/Uppsala-']")
        source_item_id = card.attributes.get("data-object-id")
        href = link.attributes.get("href") if link else None
        address = _text(card.css_first(".object-card__address"))
        if not source_item_id or not href or not address:
            raise ValueError("Heimstaden card is missing stable identity, URL or address")
        items.append(
            {
                "source_item_id": source_item_id,
                "source_url": href,
                "address": address,
                "city": "Uppsala",
                "municipality_code": "0380",
                "rooms": _number(_text(card.css_first(".object-card__data-rooms"))),
                "area_m2": _number(_text(card.css_first(".object-card__data-size"))),
                "monthly_rent": _number(_text(card.css_first(".object-card__data-prize"))),
                "available_from": _swedish_date(
                    _text(card.css_first(".object-card__availability"))
                ),
                "property_type": "rental",
                "publisher_name": "Heimstaden",
                "upstream_provider_key": "heimstaden",
                "upstream_provider_name": "Heimstaden",
                "categories": ["hyresrätt", "direktkanal"],
                "data_mode": data_mode,
                "attribution": "Källa: Heimstaden",
            }
        )
    if not items:
        if explicit_empty:
            return []
        raise ValueError("Heimstaden page contained no Uppsala apartment cards")
    if explicit_empty:
        raise ValueError("Heimstaden zero count contradicts Uppsala apartment cards")
    if len(items) > max_items:
        raise ValueError(f"Heimstaden result exceeds configured cap ({max_items})")
    if len({item["source_item_id"] for item in items}) != len(items):
        raise ValueError("Heimstaden page contains duplicate listing identifiers")
    return items


class HeimstadenUppsalaAdapter(SourceAdapter):
    source_key = "heimstaden_uppsala_rentals"

    async def fetch(self) -> FetchResult[dict[str, Any]]:
        settings = get_settings()
        if not settings.heimstaden_live_enabled:
            raise ValueError("Heimstaden live collection is disabled by configuration")
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": settings.heimstaden_user_agent},
        ) as client:
            response = await client.get(settings.heimstaden_uppsala_url)
            response.raise_for_status()
            html = response.text
        items = parse_uppsala_page(
            html,
            data_mode="live",
            max_items=settings.heimstaden_max_items,
        )
        return FetchResult(
            items,
            SnapshotEvidence(
                requests_attempted=1,
                requests_succeeded=1,
                requests_failed=0,
                pages_received=1,
                items_received=len(items),
                hit_result_limit=len(items) >= settings.heimstaden_max_items,
                inventory_scope_complete=False,
                rule_version="heimstaden-public-search",
                reasons=("public_search_is_not_a_verified_complete_inventory",),
                evidence={"transport": "html", "scope": "Uppsala public search"},
            ),
        )

    def normalize(self, item: dict[str, Any]) -> NormalizedItem:
        return normalize_item(item)
