import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import or_, select

from flyttsignal.config import get_settings
from flyttsignal.db.models import RunStatus, RunTrigger, Source, SourceRun
from flyttsignal.db.session import SessionLocal
from flyttsignal.domains.listings.lifecycle import ListingLifecyclePolicy
from flyttsignal.ingestion.pipelines.address_enrichment import (
    execute_address_enrichment_source,
)
from flyttsignal.ingestion.pipelines.benchmark_statistics import (
    execute_benchmark_statistics_source,
)
from flyttsignal.ingestion.pipelines.rental_developments import (
    execute_rental_development_source,
)
from flyttsignal.ingestion.pipelines.rental_listings import execute_rental_listing_source
from flyttsignal.ingestion.pipelines.spatial_features import execute_spatial_feature_source
from flyttsignal.integrations.sources.address_enrichment.lantmateriet import (
    LantmaterietAddressAdapter,
)
from flyttsignal.integrations.sources.benchmark_statistics.scb import SCBMigrationAdapter
from flyttsignal.integrations.sources.rental_developments.homeq import (
    HomeQPublicUppsalaProjectAdapter,
)
from flyttsignal.integrations.sources.rental_listings.heimstaden import HeimstadenUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.homeq import HomeQPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.hsb import HSBPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    UppsalaBostadsformedlingAdapter,
)
from flyttsignal.integrations.sources.spatial_features.uppsala_open_data import (
    UppsalaBuildingsAdapter,
)

ADAPTERS = {
    UppsalaBostadsformedlingAdapter.source_key: UppsalaBostadsformedlingAdapter,
    HeimstadenUppsalaAdapter.source_key: HeimstadenUppsalaAdapter,
    HomeQPublicUppsalaAdapter.source_key: HomeQPublicUppsalaAdapter,
    HSBPublicUppsalaAdapter.source_key: HSBPublicUppsalaAdapter,
}
BENCHMARK_ADAPTERS = {SCBMigrationAdapter.source_key: SCBMigrationAdapter}
ADDRESS_ENRICHMENT_ADAPTERS = {LantmaterietAddressAdapter.source_key: LantmaterietAddressAdapter}
SPATIAL_FEATURE_ADAPTERS = {UppsalaBuildingsAdapter.source_key: UppsalaBuildingsAdapter}
DEVELOPMENT_ADAPTERS = {
    HomeQPublicUppsalaProjectAdapter.source_key: HomeQPublicUppsalaProjectAdapter
}


def configured_live_source_states(settings) -> dict[str, bool]:
    return {
        UppsalaBostadsformedlingAdapter.source_key: (
            settings.uppsala_bostadsformedling_live_enabled
        ),
        HeimstadenUppsalaAdapter.source_key: settings.heimstaden_live_enabled,
        HomeQPublicUppsalaAdapter.source_key: settings.homeq_public_live_enabled,
        HomeQPublicUppsalaProjectAdapter.source_key: settings.homeq_public_live_enabled,
        HSBPublicUppsalaAdapter.source_key: settings.hsb_public_live_enabled,
    }


def configured_listing_lifecycle_policy(settings, source_key: str) -> ListingLifecyclePolicy | None:
    if (
        source_key == UppsalaBostadsformedlingAdapter.source_key
        and settings.uppsala_bostadsformedling_listing_lifecycle_enabled
    ):
        return ListingLifecyclePolicy(
            source_key=source_key,
            completeness_rule_version="ubf-public-graphql-v2",
            grace_runs=settings.uppsala_bostadsformedling_listing_lifecycle_grace_runs,
        )
    return None


def reconcile_worker_state() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    stale_before = now - timedelta(minutes=settings.worker_stale_run_minutes)
    with SessionLocal() as session:
        for source in session.scalars(select(Source)):
            configured = configured_live_source_states(settings).get(source.key)
            if configured is not None and source.enabled != configured:
                source.enabled = configured
                source.next_run_at = None if configured else source.next_run_at
                source.status = "PENDING" if configured else "DISABLED"
            if (
                source.status == "RUNNING"
                and source.last_run_at is not None
                and source.last_run_at < stale_before
            ):
                source.status = "ERROR"
                source.next_run_at = None
                for run in session.scalars(
                    select(SourceRun).where(
                        SourceRun.source_id == source.id,
                        SourceRun.status == RunStatus.RUNNING,
                    )
                ):
                    run.status = RunStatus.FAILED
                    run.completed_at = now
                    run.error_message = "Worker restarted after a stale RUNNING state"
        session.commit()


async def run_due_once() -> int:
    settings = get_settings()
    with SessionLocal() as session:
        source = session.scalar(
            select(Source)
            .where(
                Source.enabled.is_(True),
                Source.status != "RUNNING",
                or_(Source.next_run_at.is_(None), Source.next_run_at <= datetime.now(UTC)),
            )
            .order_by(Source.next_run_at.asc().nullsfirst(), Source.key)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if source is None:
            return 0
        adapter_type = ADAPTERS.get(source.key)
        benchmark_adapter_type = BENCHMARK_ADAPTERS.get(source.key)
        address_enrichment_adapter_type = ADDRESS_ENRICHMENT_ADAPTERS.get(source.key)
        spatial_feature_adapter_type = SPATIAL_FEATURE_ADAPTERS.get(source.key)
        development_adapter_type = DEVELOPMENT_ADAPTERS.get(source.key)
        if (
            adapter_type is None
            and benchmark_adapter_type is None
            and address_enrichment_adapter_type is None
            and spatial_feature_adapter_type is None
            and development_adapter_type is None
        ):
            structlog.get_logger().warning("adapter_missing", source=source.key)
            return 0
        source.status = "RUNNING"
        session.commit()
        if adapter_type is not None:
            await execute_rental_listing_source(
                session,
                source,
                adapter_type(),
                trigger_type=RunTrigger.SCHEDULED,
                lifecycle_policy=configured_listing_lifecycle_policy(settings, source.key),
            )
        elif benchmark_adapter_type is not None:
            await execute_benchmark_statistics_source(
                session,
                source,
                benchmark_adapter_type(),
                trigger_type=RunTrigger.SCHEDULED,
            )
        elif address_enrichment_adapter_type is not None:
            await execute_address_enrichment_source(
                session,
                source,
                address_enrichment_adapter_type(),
                trigger_type=RunTrigger.SCHEDULED,
            )
        elif spatial_feature_adapter_type is not None:
            await execute_spatial_feature_source(
                session,
                source,
                spatial_feature_adapter_type(),
                trigger_type=RunTrigger.SCHEDULED,
            )
        elif development_adapter_type is not None:
            await execute_rental_development_source(
                session,
                source,
                development_adapter_type(),
                trigger_type=RunTrigger.SCHEDULED,
            )
        return 1


async def main() -> None:
    settings = get_settings()
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    reconcile_worker_state()
    while True:
        await run_due_once()
        await asyncio.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
