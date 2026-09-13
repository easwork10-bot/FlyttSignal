import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.source_runs import source_run_out
from flyttsignal.api.schemas.sources import LifecycleReadinessOut, SourceRunOut
from flyttsignal.db.repositories.dashboard import DashboardRepository
from flyttsignal.lifecycle.readiness import evaluate_lifecycle_readiness

router = APIRouter()


@router.get(
    "/source-runs",
    response_model=list[SourceRunOut],
    operation_id="listSourceRuns",
)
def list_source_runs(
    db: Db,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    source_id: uuid.UUID | None = None,
    status: Literal["RUNNING", "SUCCESS", "FAILED"] | None = None,
):
    return [
        source_run_out(run) for run in DashboardRepository(db).source_runs(limit, source_id, status)
    ]


@router.get(
    "/sources/{source_key}/lifecycle-readiness",
    response_model=LifecycleReadinessOut,
    operation_id="getSourceLifecycleReadiness",
)
def get_source_lifecycle_readiness(source_key: str, db: Db):
    repository = DashboardRepository(db)
    source = repository.source_by_key(source_key)
    if source is None:
        raise HTTPException(404, "Source not found")
    readiness = evaluate_lifecycle_readiness(repository.source_runs(limit=200, source_id=source.id))
    return LifecycleReadinessOut(
        source_key=source.key,
        status="READY" if readiness.ready else "NOT_READY",
        required_runs=readiness.required_runs,
        qualifying_runs=readiness.qualifying_runs,
        rule_version=readiness.rule_version,
        reasons=list(readiness.reasons),
        considered_run_ids=list(readiness.considered_run_ids),
        latest_scheduled_run_at=readiness.latest_scheduled_run_at,
        evaluated_at=datetime.now(UTC),
    )
