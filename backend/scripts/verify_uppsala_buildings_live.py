import asyncio
import json

from sqlalchemy import func, select

from flyttsignal.config import get_settings
from flyttsignal.db.models import Event, ScoreComponent, Signal, Source, SpatialFeature
from flyttsignal.db.session import SessionLocal
from flyttsignal.ingestion.pipelines.spatial_features import execute_spatial_feature_source
from flyttsignal.integrations.sources.spatial_features.uppsala_open_data import (
    UppsalaBuildingsAdapter,
)

LIVE_LIMIT = 5


async def main() -> None:
    if not get_settings().uppsala_open_data_live_enabled:
        raise RuntimeError(
            "Set UPPSALA_OPEN_DATA_LIVE_ENABLED=true for this controlled process only"
        )
    with SessionLocal() as session:
        source = session.scalar(
            select(Source).where(Source.key == UppsalaBuildingsAdapter.source_key)
        )
        if source is None:
            raise ValueError("Uppsala Open Data source migration is missing")
        if source.enabled:
            raise AssertionError("Controlled verification requires the database source disabled")
        before_events = session.scalar(select(func.count()).select_from(Event)) or 0
        before_signals = session.scalar(select(func.count()).select_from(Signal)) or 0
        before_components = session.scalar(select(func.count()).select_from(ScoreComponent)) or 0

        first = await execute_spatial_feature_source(
            session,
            source,
            UppsalaBuildingsAdapter(page_size=LIVE_LIMIT, max_features=LIVE_LIMIT),
        )
        second = await execute_spatial_feature_source(
            session,
            source,
            UppsalaBuildingsAdapter(page_size=LIVE_LIMIT, max_features=LIVE_LIMIT),
        )

        live_count = (
            session.scalar(
                select(func.count())
                .select_from(SpatialFeature)
                .where(SpatialFeature.data_mode == "live")
            )
            or 0
        )
        after_events = session.scalar(select(func.count()).select_from(Event)) or 0
        after_signals = session.scalar(select(func.count()).select_from(Signal)) or 0
        after_components = session.scalar(select(func.count()).select_from(ScoreComponent)) or 0
        if first.status.value != "SUCCESS" or first.items_seen != LIVE_LIMIT:
            raise AssertionError("Controlled live run did not return the bounded feature count")
        if second.items_new or second.items_changed:
            raise AssertionError("Controlled live rerun was not idempotent")
        if live_count != LIVE_LIMIT or source.enabled:
            raise AssertionError("Controlled live storage or source enablement is unsafe")
        if (after_events, after_signals, after_components) != (
            before_events,
            before_signals,
            before_components,
        ):
            raise AssertionError("Controlled live run changed signal-domain records")
        print(
            json.dumps(
                {
                    "first": {
                        "seen": first.items_seen,
                        "new": first.items_new,
                        "changed": first.items_changed,
                    },
                    "second": {
                        "seen": second.items_seen,
                        "new": second.items_new,
                        "changed": second.items_changed,
                    },
                    "live_features": live_count,
                    "events_delta": after_events - before_events,
                    "signals_delta": after_signals - before_signals,
                    "score_components_delta": after_components - before_components,
                    "source_enabled": source.enabled,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
