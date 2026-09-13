import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    Base,
    BenchmarkObservation,
    RawItem,
    RunStatus,
    Scope,
    Source,
    SourceRun,
    SourceType,
)
from flyttsignal.ingestion.pipelines.benchmark_statistics import (
    execute_benchmark_statistics_source,
)
from flyttsignal.integrations.sources.benchmark_statistics.scb import SCBMigrationAdapter

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "benchmark_statistics"
    / "scb"
    / "uppsala-migration-2025.json"
)


def fixture_payload() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def fixture_envelope() -> dict[str, Any]:
    return {
        "source_item_id": "TAB6640:0380:2025:total",
        "source_url": "https://api.scb.se/example",
        "payload": fixture_payload(),
    }


def test_scb_fixture_normalizes_nine_aggregate_metrics() -> None:
    observations = SCBMigrationAdapter(live_enabled=False).normalize(fixture_envelope())
    assert len(observations) == 9
    assert {item.metric_key for item in observations} == {
        "0000086B",
        "0000086F",
        "00000869",
        "00000867",
        "00000868",
        "0000086A",
        "0000086D",
        "0000086E",
        "0000086C",
    }
    assert {item.municipality_code for item in observations} == {"0380"}
    assert {item.period for item in observations} == {"2025"}
    assert observations[0].value == 16319


def test_scb_schema_drift_fails_closed() -> None:
    envelope = fixture_envelope()
    envelope["payload"] = copy.deepcopy(envelope["payload"])
    envelope["payload"]["id"] = ["Region", "ContentsCode", "Tid"]
    with pytest.raises(ValueError, match="schema drift"):
        SCBMigrationAdapter(live_enabled=False).normalize(envelope)


def test_scb_live_kill_switch_defaults_closed() -> None:
    adapter = SCBMigrationAdapter(live_enabled=False)
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(adapter.fetch())


def test_scb_fetch_uses_approved_query_and_retries_transient_failure() -> None:
    payload = fixture_payload()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, headers={"Retry-After": "0"}, request=request)
        return httpx.Response(200, json=payload, request=request)

    async def no_sleep(_: float) -> None:
        return None

    async def run() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = SCBMigrationAdapter(
                client=client, live_enabled=True, max_retries=1, sleep=no_sleep
            )
            return await adapter.fetch()

    result = asyncio.run(run())
    assert len(requests) == 2
    query = requests[-1].url.params
    assert query["valueCodes[Region]"] == "0380"
    assert query["valueCodes[Alder]"] == "TOT1"
    assert query["valueCodes[Kon]"] == "TotSa"
    assert query["valueCodes[Tid]"] == "top(1)"
    assert result[0]["source_item_id"] == "TAB6640:0380:2025:total"


def test_scb_fetch_rejects_oversized_response() -> None:
    payload = fixture_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = SCBMigrationAdapter(
                client=client,
                live_enabled=True,
                max_response_bytes=100,
                max_retries=0,
            )
            await adapter.fetch()

    with pytest.raises(ValueError, match="size limit"):
        asyncio.run(run())


class FixtureSCBAdapter(SCBMigrationAdapter):
    async def fetch(self) -> list[dict[str, Any]]:
        return [fixture_envelope()]


def test_benchmark_pipeline_is_idempotent_and_property_free() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = [
        Source.__table__,
        SourceRun.__table__,
        RawItem.__table__,
        BenchmarkObservation.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        source = Source(
            key="scb_pxweb_migration",
            name="SCB PxWeb migration benchmark",
            source_type=SourceType.PUBLIC_API,
            scope=Scope.NATIONAL,
            access_method="fixture",
            enabled=True,
            poll_interval_minutes=10080,
            status="PENDING",
        )
        session.add(source)
        session.commit()

        first = asyncio.run(
            execute_benchmark_statistics_source(session, source, FixtureSCBAdapter())
        )
        second = asyncio.run(
            execute_benchmark_statistics_source(session, source, FixtureSCBAdapter())
        )

        assert first.status == RunStatus.SUCCESS
        assert first.items_new == 1
        assert second.status == RunStatus.SUCCESS
        assert second.items_new == 0
        assert second.items_changed == 0
        assert session.scalar(select(func.count()).select_from(RawItem)) == 1
        assert session.scalar(select(func.count()).select_from(BenchmarkObservation)) == 9
