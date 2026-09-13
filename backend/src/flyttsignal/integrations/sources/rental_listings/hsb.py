import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser, Node

from flyttsignal.config import get_settings
from flyttsignal.ingestion.contracts import (
    FetchResult,
    SnapshotEvidence,
    SourceAdapter,
)
from flyttsignal.normalization.service import NormalizedItem, normalize_item


def _text(node: Node | None) -> str:
    return " ".join(node.text(separator=" ", strip=True).split()) if node else ""


def _deadline(value: str, *, today: date | None = None) -> str | None:
    value = " ".join(value.strip().split())
    current = today or date.today()
    if value.casefold() == "i dag":
        return current.isoformat()
    if value.casefold() == "i morgon":
        return (current + timedelta(days=1)).isoformat()
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else None


def _reported_availability(document: HTMLParser) -> tuple[int | None, int | None, int]:
    property_cards = document.css(".property-grid-card")
    if not property_cards:
        return None, None, 0

    county_total = 0
    uppsala_total = 0
    for card in property_cards:
        link = card if card.tag == "a" else card.css_first("a[href*='/fastigheter/']")
        href = link.attributes.get("href", "") if link else ""
        available = re.search(r"(\d+)\s+ledig(?:a)?\s+lägenhet", _text(card), re.IGNORECASE)
        if not href or not available:
            return None, None, len(property_cards)
        count = int(available.group(1))
        county_total += count
        if "/uppsala/uppsala/fastigheter/" in href.casefold():
            uppsala_total += count
    return county_total, uppsala_total, len(property_cards)


def parse_uppsala_search(html: str, *, max_items: int) -> list[dict[str, Any]]:
    document = HTMLParser(html)
    cards = document.css(".apartment-block")
    if not cards:
        county_reported, uppsala_reported, _ = _reported_availability(document)
        if county_reported == 0 and uppsala_reported == 0:
            return []
        raise ValueError("HSB listing-card schema not found")
    items: list[dict[str, Any]] = []
    for card in cards:
        link = card.css_first("a[href*='/fastigheter/']")
        href = link.attributes.get("href", "") if link else ""
        if "/uppsala/uppsala/fastigheter/" not in href.casefold():
            continue
        identity = re.search(r"/fastigheter/([^/]+/[^/]+)/?$", href, re.IGNORECASE)
        address = _text(card.css_first(".apartment-block__details h4"))
        location = _text(card.css_first(".apartment-block__details-location"))
        detail_text = _text(card.css_first(".apartment-block__details"))
        facts = re.search(
            r"(?P<rooms>\d+(?:[.,]\d+)?)\s+rok\s*\|\s*"
            r"(?P<area>\d+(?:[.,]\d+)?)\s+kvm.*?Hyra\s+"
            r"(?P<rent>[\d\s\xa0]+)\s*kr",
            detail_text,
            re.IGNORECASE,
        )
        move_in = re.search(r"Inflytt:\s*(\d{4}-\d{2}-\d{2})", detail_text)
        deadline_text = _text(card.css_first(".apartment-block__showtimes"))
        banner = _text(card.css_first(".apartment-block__banner span"))
        if not identity or not address or not location.startswith("Uppsala,") or not facts:
            raise ValueError("HSB Uppsala card is missing identity, address or housing facts")
        categories = ["hyresrätt", "direktkanal", "publik-sökning"]
        if banner:
            categories.append(banner)
        items.append(
            {
                "source_item_id": identity.group(1),
                "source_url": urljoin("https://www.hsb.se", href),
                "address": address,
                "city": "Uppsala",
                "municipality_code": "0380",
                "rooms": facts.group("rooms").replace(",", "."),
                "area_m2": facts.group("area").replace(",", "."),
                "monthly_rent": re.sub(r"\D", "", facts.group("rent")),
                "available_from": move_in.group(1) if move_in else None,
                "application_deadline": _deadline(
                    deadline_text.removeprefix("Sista anmälningsdag:").strip()
                ),
                "property_type": "rental",
                "publisher_name": "HSB",
                "upstream_provider_key": "hsb-uppsala",
                "upstream_provider_name": "HSB Uppsala",
                "categories": categories,
                "data_mode": "live",
                "attribution": "Källa: HSB",
            }
        )
    _, uppsala_reported, _ = _reported_availability(document)
    if not items and uppsala_reported != 0:
        raise ValueError("HSB returned no Uppsala listings")
    if len(items) > max_items:
        raise ValueError(f"HSB Uppsala result exceeds configured cap ({max_items})")
    if len({item["source_item_id"] for item in items}) != len(items):
        raise ValueError("HSB returned duplicate listing identifiers")
    return items


def hsb_snapshot_evidence(
    html: str, items: list[dict[str, Any]], *, max_items: int
) -> SnapshotEvidence:
    document = HTMLParser(html)
    county_reported, uppsala_reported, property_count = _reported_availability(document)
    county_received = len(document.css(".apartment-block"))
    has_pagination = bool(
        document.css("a[rel='next'], .pagination, .pager, .load-more, [data-load-more]")
    )

    reasons: list[str] = []
    if county_reported is None or uppsala_reported is None:
        reasons.append("property_inventory_counts_missing")
    elif county_received != county_reported:
        reasons.append("county_listing_count_mismatch")
    if uppsala_reported is not None and len(items) != uppsala_reported:
        reasons.append("uppsala_listing_count_mismatch")
    if has_pagination:
        reasons.append("pagination_controls_present")

    scope_complete = not reasons and property_count > 0
    if scope_complete:
        reasons.append("property_counts_match_listing_cards")

    return SnapshotEvidence(
        requests_attempted=1,
        requests_succeeded=1,
        requests_failed=0,
        pages_expected=1 if not has_pagination else None,
        pages_received=1,
        items_reported=uppsala_reported,
        items_received=len(items),
        pagination_complete=not has_pagination,
        hit_result_limit=len(items) >= max_items,
        inventory_scope_complete=scope_complete,
        rule_version="hsb-public-html-v2",
        reasons=tuple(reasons),
        evidence={
            "transport": "html",
            "scope": "Uppsala municipality within public Uppsala county search",
            "county_items_reported": county_reported,
            "county_items_received": county_received,
            "property_cards_received": property_count,
        },
    )


def _normalize_hsb(item: dict[str, Any], *, expected_mode: str) -> NormalizedItem:
    normalized = normalize_item(item)
    if normalized.data_mode != expected_mode:
        raise ValueError(f"HSB adapter expected {expected_mode} data")
    if normalized.publisher_name != "HSB":
        raise ValueError("HSB listing must preserve HSB as publisher")
    if normalized.upstream_provider_key != "hsb-uppsala":
        raise ValueError("HSB direct listings require HSB Uppsala provenance")
    return normalized


class HSBPublicUppsalaAdapter(SourceAdapter):
    """Bounded parser for HSB's direct public Uppsala search."""

    source_key = "hsb_public_uppsala_live_rentals"

    async def fetch(self) -> FetchResult[dict[str, Any]]:
        settings = get_settings()
        if not settings.hsb_public_live_enabled:
            raise ValueError("HSB live collection is disabled by configuration")
        async with httpx.AsyncClient(
            timeout=settings.hsb_public_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.hsb_public_user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            response = await client.get(settings.hsb_public_uppsala_url)
            response.raise_for_status()
        items = parse_uppsala_search(response.text, max_items=settings.hsb_public_max_items)
        return FetchResult(
            items,
            hsb_snapshot_evidence(
                response.text,
                items,
                max_items=settings.hsb_public_max_items,
            ),
        )

    def normalize(self, item: dict[str, Any]) -> NormalizedItem:
        return _normalize_hsb(item, expected_mode="live")
