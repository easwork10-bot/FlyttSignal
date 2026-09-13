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
    RawItem,
    RunStatus,
    Scope,
    Source,
    SourceRun,
    SourceType,
    SpatialFeature,
)
from flyttsignal.ingestion.pipelines.spatial_features import execute_spatial_feature_source
from flyttsignal.integrations.sources.spatial_features.uppsala_open_data import (
    ATTRIBUTION,
    DATASET_KEY,
    LIVE_FILTER,
    OUT_FIELDS,
    UppsalaBuildingsAdapter,
)
from scripts.verify_uppsala_buildings_fixture import fixture_identity_matches

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "spatial_features"
    / "uppsala_open_data"
    / "buildings.geojson"
)


@pytest.mark.parametrize(
    ("fixture_ids", "live_count", "expected"),
    [
        ({"1", "2", "3"}, 0, True),
        ({"1", "2", "3"}, 5, True),
        ({"1", "2"}, 5, False),
        ({"1", "2", "3", "4"}, 5, False),
    ],
)
def test_fixture_verification_owns_only_exact_fixture_set(
    fixture_ids: set[str], live_count: int, expected: bool
) -> None:
    rows = [("fixture", item_id) for item_id in fixture_ids]
    rows.extend(("live", f"live-{index}") for index in range(live_count))
    assert fixture_identity_matches(rows, {"1", "2", "3"}) is expected


def fixture_features() -> list[dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return payload["features"]


def fixture_envelopes() -> list[dict[str, Any]]:
    return [
        {
            "data_mode": "fixture",
            "dataset_key": DATASET_KEY,
            "municipality_code": "0380",
            "source_item_id": str(feature["properties"]["OBJECTID"]),
            "source_url": "https://opendata.uppsala.se/example/fixture",
            "payload": feature,
        }
        for feature in fixture_features()
    ]


def test_fixture_normalizes_building_context_and_geometry() -> None:
    adapter = UppsalaBuildingsAdapter(live_enabled=False)
    approved = adapter.normalize(fixture_envelopes()[0])
    multi = adapter.normalize(fixture_envelopes()[2])

    assert approved.dataset_key == DATASET_KEY
    assert approved.subtype_label == "Bostad"
    assert approved.status_label == "Befintligt"
    assert approved.activity_label == "Godkänt bygglov"
    assert approved.geometry_wkt.startswith("POLYGON((")
    assert approved.attribution == ATTRIBUTION
    assert approved.data_mode == "fixture"
    assert approved.source_attributes["score_neutral"] is True
    assert multi.geometry_wkt.startswith("MULTIPOLYGON(((")


def test_schema_codes_and_geometry_fail_closed() -> None:
    adapter = UppsalaBuildingsAdapter(live_enabled=False)

    unknown_code = copy.deepcopy(fixture_envelopes()[0])
    unknown_code["payload"]["properties"]["ACTIVITYTYPE"] = 99
    with pytest.raises(ValueError, match="unknown building activity"):
        adapter.normalize(unknown_code)

    unknown_field = copy.deepcopy(fixture_envelopes()[0])
    unknown_field["payload"]["properties"]["owner"] = "not accepted"
    with pytest.raises(ValueError, match="schema drift"):
        adapter.normalize(unknown_field)

    open_ring = copy.deepcopy(fixture_envelopes()[0])
    open_ring["payload"]["geometry"]["coordinates"][0][-1] = [17.0, 59.0]
    with pytest.raises(ValueError, match="not closed"):
        adapter.normalize(open_ring)


def test_live_kill_switch_defaults_closed() -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(UppsalaBuildingsAdapter(live_enabled=False).fetch())


def test_live_fetch_is_bounded_and_paginated() -> None:
    features = fixture_features()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        offset = int(request.url.params["resultOffset"])
        count = int(request.url.params["resultRecordCount"])
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": features[offset : offset + count]},
            headers={"Content-Type": "application/geo+json"},
            request=request,
        )

    async def run() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = UppsalaBuildingsAdapter(
                client=client,
                live_enabled=True,
                page_size=2,
                max_features=3,
                max_retries=0,
            )
            return await adapter.fetch()

    result = asyncio.run(run())
    assert [item["source_item_id"] for item in result] == ["9000001", "9000002", "9000003"]
    assert [request.url.params["resultOffset"] for request in requests] == ["0", "2"]
    assert all(request.url.params["where"] == LIVE_FILTER for request in requests)
    assert all(request.url.params["outFields"] == OUT_FIELDS for request in requests)
    assert all(request.url.params["outSR"] == "4326" for request in requests)


class FixtureSpatialAdapter(UppsalaBuildingsAdapter):
    async def fetch(self) -> list[dict[str, Any]]:
        return fixture_envelopes()


class ChangedFixtureSpatialAdapter(UppsalaBuildingsAdapter):
    async def fetch(self) -> list[dict[str, Any]]:
        changed = copy.deepcopy(fixture_envelopes()[0])
        changed["payload"]["properties"]["ACTIVITYTYPE"] = 4
        return [changed]


def test_spatial_pipeline_baselines_idempotently_and_tracks_later_change() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = [
        Source.__table__,
        SourceRun.__table__,
        RawItem.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE spatial_features (
              id TEXT PRIMARY KEY, source_id TEXT NOT NULL, raw_item_id TEXT NOT NULL,
              dataset_key TEXT NOT NULL, source_item_id TEXT NOT NULL,
              municipality_code TEXT NOT NULL, feature_type TEXT NOT NULL,
              subtype_code INTEGER NOT NULL, subtype_label TEXT NOT NULL,
              status_code INTEGER NOT NULL, status_label TEXT NOT NULL,
              activity_code INTEGER, activity_label TEXT, source_modified_at DATETIME,
              geometry TEXT NOT NULL, attribution TEXT NOT NULL,
              source_attributes JSON NOT NULL, data_mode TEXT NOT NULL,
              is_baseline BOOLEAN NOT NULL, observed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(source_id, dataset_key, source_item_id)
            )
        """)
    with Session(engine) as session:
        source = Source(
            key=UppsalaBuildingsAdapter.source_key,
            name="Uppsala Open Data — Byggnader",
            source_type=SourceType.OPEN_DATA,
            scope=Scope.LOCAL,
            access_method="fixture",
            enabled=False,
            poll_interval_minutes=1440,
            status="PENDING",
        )
        session.add(source)
        session.commit()

        first = asyncio.run(
            execute_spatial_feature_source(
                session, source, FixtureSpatialAdapter(live_enabled=False)
            )
        )
        second = asyncio.run(
            execute_spatial_feature_source(
                session, source, FixtureSpatialAdapter(live_enabled=False)
            )
        )
        changed = asyncio.run(
            execute_spatial_feature_source(
                session, source, ChangedFixtureSpatialAdapter(live_enabled=False)
            )
        )

        assert first.status == RunStatus.SUCCESS
        assert first.items_new == 3
        assert second.status == RunStatus.SUCCESS
        assert second.items_new == 0
        assert second.items_changed == 0
        assert changed.status == RunStatus.SUCCESS
        assert changed.items_changed == 1
        assert session.scalar(select(func.count()).select_from(RawItem)) == 3
        assert session.scalar(select(func.count()).select_from(SpatialFeature)) == 3
        updated = session.scalar(
            select(SpatialFeature).where(SpatialFeature.source_item_id == "9000001")
        )
        assert updated is not None
        assert updated.activity_label == "Ändrad byggnadsinformation"
        assert updated.is_baseline is False
