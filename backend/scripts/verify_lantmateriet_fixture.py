import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from flyttsignal.db.models import (
    AddressEnrichment,
    AddressRegisterUnitLink,
    Event,
    Signal,
    Source,
)
from flyttsignal.db.session import SessionLocal
from flyttsignal.ingestion.contracts import AddressEnrichmentTarget
from flyttsignal.ingestion.pipelines.address_enrichment import (
    execute_address_enrichment_source,
)
from flyttsignal.integrations.sources.address_enrichment.lantmateriet import (
    LantmaterietAddressAdapter,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "address_enrichment"
    / "lantmateriet"
    / "uppsala-belagenhetsadress-v4.2.json"
)
EXTERNAL_ID = "11111111-2222-4333-8444-555555555555"


class FixtureLantmaterietAdapter(LantmaterietAddressAdapter):
    async def fetch(self, targets: list[AddressEnrichmentTarget]) -> list[dict[str, Any]]:
        target = next((item for item in targets if item.address == "Testgatan 12"), None)
        if target is None:
            raise ValueError("Seed address Testgatan 12 is missing")
        return [
            {
                "data_mode": "fixture",
                "source_item_id": EXTERNAL_ID,
                "source_url": "https://geotorget.lantmateriet.se/example/fixture",
                "target_address_id": str(target.address_id),
                "query": {
                    "address": target.address,
                    "municipality_code": target.municipality_code,
                },
                "payload": json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
            }
        ]


async def main() -> None:
    with SessionLocal() as session:
        source = session.scalar(
            select(Source).where(Source.key == LantmaterietAddressAdapter.source_key)
        )
        if source is None:
            raise ValueError("Lantmäteriet source migration is missing")
        before_events = session.scalar(select(func.count()).select_from(Event)) or 0
        before_signals = session.scalar(select(func.count()).select_from(Signal)) or 0
        before_enrichments = (
            session.scalar(select(func.count()).select_from(AddressEnrichment)) or 0
        )

        first = await execute_address_enrichment_source(
            session, source, FixtureLantmaterietAdapter(live_enabled=False)
        )
        second = await execute_address_enrichment_source(
            session, source, FixtureLantmaterietAdapter(live_enabled=False)
        )

        after_events = session.scalar(select(func.count()).select_from(Event)) or 0
        after_signals = session.scalar(select(func.count()).select_from(Signal)) or 0
        enrichment_count = session.scalar(select(func.count()).select_from(AddressEnrichment)) or 0
        register_unit_count = (
            session.scalar(select(func.count()).select_from(AddressRegisterUnitLink)) or 0
        )
        if after_events != before_events or after_signals != before_signals:
            raise AssertionError("Address enrichment changed event or signal counts")
        expected_first_new = 1 if before_enrichments == 0 else 0
        if (
            first.items_new != expected_first_new
            or second.items_new != 0
            or second.items_changed != 0
        ):
            raise AssertionError("Fixture verification was not idempotent")
        if source.enabled or enrichment_count != 1 or register_unit_count != 1:
            raise AssertionError("Source enablement or enrichment count is unsafe")
        print(
            json.dumps(
                {
                    "first": {
                        "new": first.items_new,
                        "changed": first.items_changed,
                    },
                    "second": {
                        "new": second.items_new,
                        "changed": second.items_changed,
                    },
                    "address_enrichments": enrichment_count,
                    "address_register_unit_links": register_unit_count,
                    "events_delta": after_events - before_events,
                    "signals_delta": after_signals - before_signals,
                    "source_enabled": source.enabled,
                    "preexisting_enrichment": before_enrichments > 0,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
