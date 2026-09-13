import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    BenchmarkObservation,
    RawItem,
    RunStatus,
    RunTrigger,
    Source,
    SourceRun,
)
from flyttsignal.ingestion.change_detection import classify_change, content_hash
from flyttsignal.ingestion.contracts import BenchmarkAdapter

log = structlog.get_logger()


async def execute_benchmark_statistics_source(
    session: Session,
    source: Source,
    adapter: BenchmarkAdapter,
    *,
    trigger_type: RunTrigger = RunTrigger.MANUAL,
) -> SourceRun:
    """Persist aggregate context without entering the property/event/signal pipeline."""

    started = time.monotonic()
    run = SourceRun(source_id=source.id, status=RunStatus.RUNNING, trigger_type=trigger_type.value)
    source.status = "RUNNING"
    source.last_run_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    try:
        payloads = await adapter.fetch()
        if not payloads:
            raise ValueError("Benchmark adapter returned no snapshots")
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

            for item in adapter.normalize(parsed):
                dimension_key = content_hash(item.dimensions)
                observation = session.scalar(
                    select(BenchmarkObservation).where(
                        BenchmarkObservation.source_id == source.id,
                        BenchmarkObservation.dataset_key == item.dataset_key,
                        BenchmarkObservation.dimension_key == dimension_key,
                        BenchmarkObservation.metric_key == item.metric_key,
                        BenchmarkObservation.period == item.period,
                    )
                )
                if observation is None:
                    observation = BenchmarkObservation(
                        source_id=source.id,
                        raw_item_id=raw.id,
                        dataset_key=item.dataset_key,
                        dimension_key=dimension_key,
                        metric_key=item.metric_key,
                        municipality_code=item.municipality_code,
                        period=item.period,
                        value=item.value,
                        unit=item.unit,
                        dimensions=item.dimensions,
                        source_updated_at=item.source_updated_at,
                    )
                    session.add(observation)
                else:
                    observation.raw_item_id = raw.id
                    observation.value = item.value
                    observation.unit = item.unit
                    observation.dimensions = item.dimensions
                    observation.source_updated_at = item.source_updated_at
                    observation.updated_at = datetime.now(UTC)

        now = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.completed_at = now
        run.duration_ms = round((time.monotonic() - started) * 1000)
        source.status = "HEALTHY"
        source.last_success_at = now
        source.next_run_at = now + timedelta(minutes=source.poll_interval_minutes)
        session.commit()
        log.info(
            "benchmark_source_run_completed",
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
        log.exception("benchmark_source_run_failed", source=source.key)
        return failed_run
