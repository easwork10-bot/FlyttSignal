from typing import Any

from flyttsignal.domains.housing_providers.identity import canonical_provider_key


def homeq_provider_key(name: str, provider_id: object) -> str:
    return canonical_provider_key(name, "homeq-landlord", provider_id)


def parse_homeq_search_response(
    payload: dict[str, Any], *, max_items: int, allow_empty: bool = False
) -> tuple[list[dict], int]:
    results = payload.get("results")
    total_hits = payload.get("total_hits")
    if not isinstance(results, list) or not isinstance(total_hits, int):
        raise ValueError("HomeQ search schema not found")
    minimum = 0 if allow_empty else 1
    if total_hits < minimum or total_hits > max_items:
        raise ValueError(f"HomeQ result count is outside configured bounds ({minimum}-{max_items})")
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("HomeQ search result must be an object")
    return results, total_hits
