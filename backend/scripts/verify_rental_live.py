"""Read and normalize every enabled public rental source without database writes."""

import asyncio
import json

from flyttsignal.ingestion.snapshot_integrity import assess_snapshot
from flyttsignal.integrations.sources.rental_listings.heimstaden import HeimstadenUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.homeq import HomeQPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.hsb import HSBPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    UppsalaBostadsformedlingAdapter,
)


async def _summary(adapter) -> dict[str, int | bool]:
    result = await adapter.fetch()
    listings = [adapter.normalize(item) for item in result]
    if any(item.city != "Uppsala" for item in listings):
        raise AssertionError(f"{adapter.source_key} returned a listing outside Uppsala")
    identifiers = {item.source_item_id for item in listings}
    if len(identifiers) != len(listings):
        raise AssertionError(f"{adapter.source_key} returned duplicate identifiers")
    return {
        "listings": len(listings),
        "providers": len({item.upstream_provider_key for item in listings}),
        "snapshot_status": assess_snapshot(result.snapshot).status.value,
    }


async def main() -> None:
    adapters = (
        UppsalaBostadsformedlingAdapter(),
        HeimstadenUppsalaAdapter(),
        HomeQPublicUppsalaAdapter(),
        HSBPublicUppsalaAdapter(),
    )
    result = {}
    for adapter in adapters:
        result[adapter.source_key] = await _summary(adapter)
    result["database_writes"] = 0
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
