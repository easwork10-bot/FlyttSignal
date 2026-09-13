"""Read and validate the public UBF inventory without database writes."""

import asyncio
import json

from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus, assess_snapshot
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    UppsalaBostadsformedlingAdapter,
)


async def main() -> None:
    adapter = UppsalaBostadsformedlingAdapter()
    result = await adapter.fetch()
    assessment = assess_snapshot(result.snapshot)
    if assessment.status is SnapshotStatus.COMPLETE:
        raise RuntimeError("UBF live completeness has not been independently verified")

    listings = [adapter.normalize(item) for item in result]
    identifiers = {listing.source_item_id for listing in listings}
    providers = {listing.upstream_provider_key for listing in listings}
    if len(identifiers) != len(listings):
        raise AssertionError("Live verification returned duplicate listing identifiers")
    if any(listing.city != "Uppsala" for listing in listings):
        raise AssertionError("Live verification returned a listing outside Uppsala")

    print(
        json.dumps(
            {
                "uppsala_objects": len(listings),
                "providers": len(providers),
                "snapshot_status": assessment.status.value,
                "database_writes": 0,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
