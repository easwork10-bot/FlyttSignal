import asyncio
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from flyttsignal.db.models import Event, ScoreComponent, Signal, Source, SpatialFeature
from flyttsignal.db.session import SessionLocal
from flyttsignal.ingestion.pipelines.spatial_features import execute_spatial_feature_source
from flyttsignal.integrations.sources.spatial_features.uppsala_open_data import (
    DATASET_KEY,
    UppsalaBuildingsAdapter,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "spatial_features"
    / "uppsala_open_data"
    / "buildings.geojson"
)


def fixture_identity_matches(scoped_rows: Iterable[tuple[str, str]], expected: set[str]) -> bool:
    actual = {source_item_id for data_mode, source_item_id in scoped_rows if data_mode == "fixture"}
    return actual == expected


class FixtureUppsalaBuildingsAdapter(UppsalaBuildingsAdapter):
    async def fetch(self) -> list[dict[str, Any]]:
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        return [
            {
                "data_mode": "fixture",
                "dataset_key": DATASET_KEY,
                "municipality_code": "0380",
                "source_item_id": str(feature["properties"]["OBJECTID"]),
                "source_url": "https://opendata.uppsala.se/example/fixture",
                "payload": feature,
            }
            for feature in payload["features"]
        ]


async def main() -> None:
    with SessionLocal() as session:
        source = session.scalar(
            select(Source).where(Source.key == UppsalaBuildingsAdapter.source_key)
        )
        if source is None:
            raise ValueError("Uppsala Open Data source migration is missing")
        fixture_ids = {
            str(feature["properties"]["OBJECTID"])
            for feature in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["features"]
        }
        fixture_scope = (
            SpatialFeature.source_id == source.id,
            SpatialFeature.dataset_key == DATASET_KEY,
            SpatialFeature.data_mode == "fixture",
        )
        before_fixture_ids = set(
            session.scalars(select(SpatialFeature.source_item_id).where(*fixture_scope))
        )
        live_before = set(
            session.execute(
                select(SpatialFeature.id, SpatialFeature.updated_at).where(
                    SpatialFeature.source_id == source.id,
                    SpatialFeature.dataset_key == DATASET_KEY,
                    SpatialFeature.data_mode == "live",
                )
            )
        )
        before_events = session.scalar(select(func.count()).select_from(Event)) or 0
        before_signals = session.scalar(select(func.count()).select_from(Signal)) or 0
        before_components = session.scalar(select(func.count()).select_from(ScoreComponent)) or 0

        first = await execute_spatial_feature_source(
            session, source, FixtureUppsalaBuildingsAdapter(live_enabled=False)
        )
        second = await execute_spatial_feature_source(
            session, source, FixtureUppsalaBuildingsAdapter(live_enabled=False)
        )

        actual_fixture_ids = set(
            session.scalars(select(SpatialFeature.source_item_id).where(*fixture_scope))
        )
        scoped_identity_rows = session.execute(
            select(SpatialFeature.data_mode, SpatialFeature.source_item_id).where(
                SpatialFeature.source_id == source.id,
                SpatialFeature.dataset_key == DATASET_KEY,
            )
        )
        baseline_count = (
            session.scalar(
                select(func.count())
                .select_from(SpatialFeature)
                .where(*fixture_scope, SpatialFeature.is_baseline.is_(True))
            )
            or 0
        )
        after_events = session.scalar(select(func.count()).select_from(Event)) or 0
        after_signals = session.scalar(select(func.count()).select_from(Signal)) or 0
        after_components = session.scalar(select(func.count()).select_from(ScoreComponent)) or 0
        live_after = set(
            session.execute(
                select(SpatialFeature.id, SpatialFeature.updated_at).where(
                    SpatialFeature.source_id == source.id,
                    SpatialFeature.dataset_key == DATASET_KEY,
                    SpatialFeature.data_mode == "live",
                )
            )
        )
        expected_first_new = len(fixture_ids - before_fixture_ids)
        if first.items_new != expected_first_new or second.items_new or second.items_changed:
            raise AssertionError("Uppsala building fixture verification was not idempotent")
        if (
            source.enabled
            or not fixture_identity_matches(scoped_identity_rows, fixture_ids)
            or baseline_count != len(fixture_ids)
            or live_after != live_before
        ):
            raise AssertionError("Uppsala building baseline or source enablement is unsafe")
        if (after_events, after_signals, after_components) != (
            before_events,
            before_signals,
            before_components,
        ):
            raise AssertionError("Spatial fixture changed events, signals or score components")
        print(
            json.dumps(
                {
                    "first": {"new": first.items_new, "changed": first.items_changed},
                    "second": {"new": second.items_new, "changed": second.items_changed},
                    "fixture_spatial_features": len(actual_fixture_ids),
                    "live_spatial_features": len(live_after),
                    "baseline_features": baseline_count,
                    "events_delta": after_events - before_events,
                    "signals_delta": after_signals - before_signals,
                    "score_components_delta": after_components - before_components,
                    "source_enabled": source.enabled,
                    "preexisting_fixture_features": bool(before_fixture_ids),
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
