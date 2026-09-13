import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    RawItem,
    RentalListing,
    RentalProject,
    RunStatus,
    RunTrigger,
    Source,
    SourceRun,
)
from flyttsignal.ingestion.change_detection import classify_change, content_hash
from flyttsignal.ingestion.contracts import RentalDevelopmentAdapter

log = structlog.get_logger()


async def execute_rental_development_source(
    session: Session,
    source: Source,
    adapter: RentalDevelopmentAdapter,
    *,
    trigger_type: RunTrigger = RunTrigger.MANUAL,
) -> SourceRun:
    started = time.monotonic()
    run = SourceRun(source_id=source.id, status=RunStatus.RUNNING, trigger_type=trigger_type.value)
    source.status = "RUNNING"
    source.last_run_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    try:
        for payload in await adapter.fetch():
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
            project = session.scalar(
                select(RentalProject).where(
                    RentalProject.source_id == source.id,
                    RentalProject.source_item_id == source_item_id,
                )
            )
            state = classify_change(raw.content_hash if raw else None, digest)
            if state == "UNCHANGED" and project is not None:
                project.last_seen_at = datetime.now(UTC)
                run.items_unchanged += 1
                session.execute(
                    update(RentalListing)
                    .where(RentalListing.project_source_item_id == source_item_id)
                    .values(rental_project_id=project.id)
                )
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
                raw.content_hash = digest
                raw.raw_payload = parsed
                raw.fetched_at = datetime.now(UTC)
                raw.source_url = parsed.get("source_url")
                run.items_changed += 1

            item = adapter.normalize(parsed)
            if project is None:
                project = RentalProject(
                    source_id=source.id,
                    raw_item_id=raw.id,
                    source_item_id=item.source_item_id,
                    canonical_url=item.source_url,
                    name=item.name,
                    upstream_provider_key=item.upstream_provider_key,
                    upstream_provider_name=item.upstream_provider_name,
                    address=item.address,
                    city=item.city,
                    municipality_code=item.municipality_code,
                    active_listing_count=item.active_listing_count,
                    status=item.status,
                    data_mode=item.data_mode,
                    attribution=item.attribution,
                )
                session.add(project)
                session.flush()
            project.raw_item_id = raw.id
            project.canonical_url = item.source_url
            project.name = item.name
            project.upstream_provider_key = item.upstream_provider_key
            project.upstream_provider_name = item.upstream_provider_name
            project.address = item.address
            project.city = item.city
            project.municipality_code = item.municipality_code
            project.planned_unit_count = item.planned_unit_count
            project.active_listing_count = item.active_listing_count
            project.rent_min = item.rent_min
            project.rent_max = item.rent_max
            project.rooms_min = item.rooms_min
            project.rooms_max = item.rooms_max
            project.area_min = item.area_min
            project.area_max = item.area_max
            project.available_from = item.available_from
            project.latitude = item.latitude
            project.longitude = item.longitude
            project.status = item.status
            project.data_mode = item.data_mode
            project.attribution = item.attribution
            project.last_seen_at = datetime.now(UTC)
            session.execute(
                update(RentalListing)
                .where(RentalListing.project_source_item_id == source_item_id)
                .values(rental_project_id=project.id)
            )

        now = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.completed_at = now
        run.duration_ms = round((time.monotonic() - started) * 1000)
        source.status = "HEALTHY"
        source.last_success_at = now
        source.next_run_at = now + timedelta(minutes=source.poll_interval_minutes)
        session.commit()
        log.info(
            "project_source_run_completed",
            source=source.key,
            items_seen=run.items_seen,
            duration_ms=run.duration_ms,
        )
        return run
    except Exception as exc:
        session.rollback()
        failed_source = session.get(Source, source.id)
        failed_run = session.get(SourceRun, run.id)
        now = datetime.now(UTC)
        failed_source.status = "ERROR"
        failed_source.next_run_at = now + timedelta(minutes=failed_source.poll_interval_minutes)
        failed_run.status = RunStatus.FAILED
        failed_run.completed_at = now
        failed_run.duration_ms = round((time.monotonic() - started) * 1000)
        failed_run.error_message = str(exc)
        session.commit()
        log.exception("project_source_run_failed", source=source.key)
        return failed_run
