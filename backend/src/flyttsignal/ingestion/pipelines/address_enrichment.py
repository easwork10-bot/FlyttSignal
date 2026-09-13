import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    Address,
    AddressEnrichment,
    AddressRegisterUnitLink,
    RawItem,
    RunStatus,
    RunTrigger,
    Source,
    SourceCity,
    SourceRun,
)
from flyttsignal.ingestion.change_detection import classify_change, content_hash
from flyttsignal.ingestion.contracts import AddressEnrichmentAdapter, AddressEnrichmentTarget
from flyttsignal.normalization.service import normalize_address

log = structlog.get_logger()


async def execute_address_enrichment_source(
    session: Session,
    source: Source,
    adapter: AddressEnrichmentAdapter,
    *,
    trigger_type: RunTrigger = RunTrigger.MANUAL,
) -> SourceRun:
    """Persist canonical address facts without entering the event or signal pipeline."""

    started = time.monotonic()
    run = SourceRun(source_id=source.id, status=RunStatus.RUNNING, trigger_type=trigger_type.value)
    source.status = "RUNNING"
    source.last_run_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    try:
        addresses = list(
            session.scalars(
                select(Address)
                .join(
                    SourceCity,
                    and_(
                        SourceCity.city_id == Address.city_id,
                        SourceCity.source_id == source.id,
                        SourceCity.enabled.is_(True),
                    ),
                )
                .order_by(Address.created_at, Address.id)
                .limit(adapter.target_limit)
            )
        )
        targets = [
            AddressEnrichmentTarget(
                address_id=address.id,
                address=address.raw_address,
                municipality_code=address.municipality_code,
            )
            for address in addresses
        ]
        payloads = await adapter.fetch(targets) if targets else []
        allowed_targets = {target.address_id for target in targets}
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
            if item.target_address_id not in allowed_targets:
                raise ValueError(
                    "Address enrichment returned an address outside the requested batch"
                )
            address = session.get(Address, item.target_address_id)
            if address is None or address.municipality_code != item.municipality_code:
                raise ValueError("Address enrichment target is missing or outside its municipality")
            if normalize_address(address.raw_address) != item.normalized_address:
                raise ValueError("Address enrichment did not exactly match the requested address")
            observation = session.scalar(
                select(AddressEnrichment).where(
                    AddressEnrichment.source_id == source.id,
                    AddressEnrichment.address_id == address.id,
                )
            )
            values = {
                "raw_item_id": raw.id,
                "external_address_id": item.external_address_id,
                "canonical_address": item.canonical_address,
                "municipality_code": item.municipality_code,
                "postal_code": item.postal_code,
                "postal_town": item.postal_town,
                "status": item.status,
                "source_srid": item.source_srid,
                "source_easting": item.source_easting,
                "source_northing": item.source_northing,
                "attribution": item.attribution,
                "source_attributes": item.source_attributes,
            }
            if observation is None:
                observation = AddressEnrichment(
                    source_id=source.id,
                    address_id=address.id,
                    **values,
                )
                session.add(observation)
                session.flush()
            else:
                for field, value in values.items():
                    setattr(observation, field, value)
                observation.updated_at = datetime.now(UTC)

            reference = item.register_unit_reference
            link = observation.register_unit_link
            if reference is None:
                if link is not None:
                    session.delete(link)
            elif link is None:
                session.add(
                    AddressRegisterUnitLink(
                        address_enrichment_id=observation.id,
                        external_register_unit_id=reference.external_register_unit_id,
                        designation=reference.designation,
                        register_unit_type=reference.register_unit_type,
                    )
                )
            else:
                link.external_register_unit_id = reference.external_register_unit_id
                link.designation = reference.designation
                link.register_unit_type = reference.register_unit_type
                link.updated_at = datetime.now(UTC)

        now = datetime.now(UTC)
        run.status = RunStatus.SUCCESS
        run.completed_at = now
        run.duration_ms = round((time.monotonic() - started) * 1000)
        source.status = "HEALTHY"
        source.last_success_at = now
        source.next_run_at = now + timedelta(minutes=source.poll_interval_minutes)
        session.commit()
        log.info(
            "address_enrichment_run_completed",
            source=source.key,
            targets=len(targets),
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
        log.exception("address_enrichment_run_failed", source=source.key)
        return failed_run
