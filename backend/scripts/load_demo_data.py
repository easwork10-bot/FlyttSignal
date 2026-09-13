"""Validate or explicitly load deterministic synthetic rental demo data."""

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from flyttsignal.db.models import RunTrigger, Source
from flyttsignal.db.session import SessionLocal
from flyttsignal.ingestion.contracts import FetchResult, SourceAdapter, complete_fixture_result
from flyttsignal.ingestion.pipelines.rental_listings import execute_rental_listing_source
from flyttsignal.normalization.service import NormalizedItem, normalize_item

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "uppsala"


@dataclass(frozen=True)
class DemoDataset:
    source_key: str
    path: Path


DATASETS = {
    "primary": DemoDataset("fake_uppsala_rentals", FIXTURE_ROOT / "rentals.json"),
    "partner": DemoDataset(
        "fake_uppsala_partner",
        FIXTURE_ROOT / "partner-rentals.json",
    ),
}


class RepositoryFixtureAdapter(SourceAdapter):
    """Explicit development adapter; never registered in scheduled runtime."""

    def __init__(self, dataset: DemoDataset):
        self.dataset = dataset
        self.source_key = dataset.source_key

    async def fetch(self) -> FetchResult[dict[str, Any]]:
        items = json.loads(self.dataset.path.read_text(encoding="utf-8"))
        return complete_fixture_result(items)

    def normalize(self, item: dict[str, Any]) -> NormalizedItem:
        normalized = normalize_item(item)
        if normalized.data_mode != "fixture":
            raise ValueError("demo datasets must contain fixture data only")
        return normalized


async def main(*, dataset_names: tuple[str, ...], apply: bool) -> dict[str, Any]:
    adapters = [RepositoryFixtureAdapter(DATASETS[name]) for name in dataset_names]
    if not apply:
        return {
            adapter.source_key: len(
                [adapter.normalize(item) for item in await adapter.fetch()]
            )
            for adapter in adapters
        }

    results: dict[str, Any] = {}
    with SessionLocal() as session:
        for adapter in adapters:
            source = session.scalar(select(Source).where(Source.key == adapter.source_key))
            if source is None:
                raise RuntimeError(f"Missing historical demo source: {adapter.source_key}")
            run = await execute_rental_listing_source(
                session,
                source,
                adapter,
                trigger_type=RunTrigger.MANUAL,
            )
            results[adapter.source_key] = {
                "status": run.status.value,
                "seen": run.items_seen,
                "new": run.items_new,
                "changed": run.items_changed,
            }
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=tuple(DATASETS), action="append")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    names = tuple(args.dataset or DATASETS)
    print(json.dumps(asyncio.run(main(dataset_names=names, apply=args.apply)), indent=2))
