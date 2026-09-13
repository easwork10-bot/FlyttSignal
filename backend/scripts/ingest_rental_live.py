"""Run one explicit persistent development ingestion for public rental sources."""

import argparse
import asyncio
import json

from sqlalchemy import select

from flyttsignal.db.models import RunStatus, RunTrigger, Source
from flyttsignal.db.session import SessionLocal
from flyttsignal.ingestion.pipelines.rental_listings import execute_rental_listing_source
from flyttsignal.integrations.sources.rental_listings.heimstaden import HeimstadenUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.homeq import HomeQPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.hsb import HSBPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    UppsalaBostadsformedlingAdapter,
)

ADAPTERS = (
    UppsalaBostadsformedlingAdapter(),
    HeimstadenUppsalaAdapter(),
    HomeQPublicUppsalaAdapter(),
    HSBPublicUppsalaAdapter(),
)


async def main(source_key: str | None = None) -> None:
    adapters = (
        tuple(adapter for adapter in ADAPTERS if adapter.source_key == source_key)
        if source_key
        else ADAPTERS
    )
    if not adapters:
        raise ValueError(f"Unknown live rental source: {source_key}")
    results = {}
    with SessionLocal() as session:
        for adapter in adapters:
            source = session.scalar(select(Source).where(Source.key == adapter.source_key))
            if source is None:
                raise RuntimeError(f"Missing migrated source: {adapter.source_key}")
            run = await execute_rental_listing_source(
                session, source, adapter, trigger_type=RunTrigger.MANUAL
            )
            results[adapter.source_key] = {
                "status": run.status.value,
                "seen": run.items_seen,
                "new": run.items_new,
                "changed": run.items_changed,
            }
            if run.status != RunStatus.SUCCESS:
                raise RuntimeError(
                    f"{adapter.source_key} failed: {run.error_message or 'unknown error'}"
                )
    print(json.dumps(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=tuple(adapter.source_key for adapter in ADAPTERS),
        help="Run one source only; omission preserves the existing all-source behavior.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.source))
