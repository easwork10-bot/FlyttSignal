import time
from datetime import UTC, datetime, timedelta

import structlog
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    RawItem,
    RunStatus,
    RunTrigger,
    Source,
    SourceRun,
    SpatialFeature,
)
from flyttsignal.ingestion.change_detection import classify_change, content_hash
from flyttsignal.ingestion.contracts import SpatialFeatureAdapter

log = structlog.get_logger()


async def execute_spatial_feature_source(
    session: Session,
    source: Source,
    adapter: SpatialFeatureAdapter,
    *,
    trigger_type: RunTrigger = RunTrigger.MANUAL,
) -> SourceRun:
    """Persist geographic context without entering the property signal pipeline."""

    started = time.monotonic()
    run = SourceRun(source_id=source.id, status=RunStatus.RUNNING, trigger_type=trigger_type.value)
    source.status = "RUNNING"
    source.last_run_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    try:
        payloads = await adapter.fetch()
        if not payloads:
            raise ValueError("Spatial feature adapter returned no features")
        for payload in payloads:
            run.items_seen += 1
            parsed = adapter.parse(payload)
            source_item_id = str(parsed["source_item_id"])
            digest = content_hash(parsed)
            raw = session.scalar(
                select(RawItem).where(
                    RawItem.source_id == source.id,
                    RawItem.source_item_id == source_item_id,
                )
            )
            state = classify_change(raw.content_hash if raw else None, digest)
            if state == "UNCHANGED":
                run.items_unchanged += 1
                continue
            if raw is None:
                raw = RawItem(
                    source_id=source.id,
                    source_item_id=source_item_id,
                    source_url=parsed.get("source_url"),
                    content_hash=digest,
                    raw_payload=parsed,
                )
                session.add(raw)
                session.flush()
                run.items_new += 1
            else:
                raw.source_url = parsed.get("source_url")
                raw.content_hash = digest
                raw.raw_payload = parsed
                raw.fetched_at = datetime.now(UTC)
                run.items_changed += 1

            item = adapter.normalize(parsed)
            if item.source_item_id != source_item_id:
                raise ValueError("Spatial feature identity changed during normalization")
            feature = session.scalar(
                select(SpatialFeature).where(
                    SpatialFeature.source_id == source.id,
                    SpatialFeature.dataset_key == item.dataset_key,
                    SpatialFeature.source_item_id == item.source_item_id,
                )
            )
            geometry = (
                item.geometry_wkt
                if session.bind is not None and session.bind.dialect.name == "sqlite"
                else WKTElement(item.geometry_wkt, srid=4326)
            )
            values = {
                "raw_item_id": raw.id,
                "municipality_code": item.municipality_code,
                "feature_type": item.feature_type,
                "subtype_code": item.subtype_code,
                "subtype_label": item.subtype_label,
                "status_code": item.status_code,
                "status_label": item.status_label,
                "activity_code": item.activity_code,
                "activity_label": item.activity_label,
                "source_modified_at": item.source_modified_at,
                "geometry": geometry,
                "attribution": item.attribution,
                "source_attributes": item.source_attributes,
                "data_mode": item.data_mode,
            }
            if feature is None:
                feature = SpatialFeature(
                    source_id=source.id,
                    dataset_key=item.dataset_key,
                    source_item_id=item.source_item_id,
                    is_baseline=True,
                    **values,
                )
                session.add(feature)
            else:
                for field, value in values.items():
                    setattr(feature, field, value)
                feature.is_baseline = False
                feature.updated_at = datetime.now(UTC)

        now = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.completed_at = now
        run.duration_ms = round((time.monotonic() - started) * 1000)
        source.status = "HEALTHY"
        source.last_success_at = now
        source.next_run_at = now + timedelta(minutes=source.poll_interval_minutes)
        session.commit()
        log.info(
            "spatial_feature_run_completed",
            source=source.key,
            items_seen=run.items_seen,
            items_new=run.items_new,
            items_changed=run.items_changed,
            items_unchanged=run.items_unchanged,
            duration_ms=run.duration_ms,
        )
        return run
    except Exception as exc:
        session.rollback()
        failed_source = session.get(Source, source.id)
        failed_run = session.get(SourceRun, run.id)
        now = datetime.now(UTC)
        if failed_source is None or failed_run is None:
            raise
        failed_source.status = "ERROR"
        failed_source.next_run_at = now + timedelta(minutes=failed_source.poll_interval_minutes)
        failed_run.status = RunStatus.FAILED
        failed_run.completed_at = now
        failed_run.duration_ms = round((time.monotonic() - started) * 1000)
        failed_run.error_message = str(exc)
        session.commit()
        log.exception("spatial_feature_run_failed", source=source.key)
        return failed_run
