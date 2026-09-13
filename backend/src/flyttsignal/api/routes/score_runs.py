import uuid

from fastapi import APIRouter, HTTPException, Query

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.score_runs import (
    ScoreRunOut,
    SignalDimensionSetOut,
)
from flyttsignal.db.repositories.score_runs import ScoreRunRepository
from flyttsignal.scoring.read_models import InconsistentScoreSet, dimension_score_payload

router = APIRouter()


@router.get(
    "/score-runs",
    response_model=list[ScoreRunOut],
    operation_id="listScoreRuns",
)
def list_score_runs(
    db: Db,
    city_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    return ScoreRunRepository(db).dimension_runs(city_id=city_id, limit=limit)


@router.get(
    "/score-runs/{run_id}",
    response_model=ScoreRunOut,
    operation_id="getScoreRun",
)
def get_score_run(run_id: uuid.UUID, db: Db):
    run = ScoreRunRepository(db).dimension_run(run_id)
    if run is None:
        raise HTTPException(404, "Dimension score run not found")
    return run


@router.get(
    "/score-runs/{run_id}/signals/{signal_id}",
    response_model=SignalDimensionSetOut,
    operation_id="getScoreRunSignalDimensions",
)
def get_score_run_signal_dimensions(run_id: uuid.UUID, signal_id: uuid.UUID, db: Db):
    repository = ScoreRunRepository(db)
    run = repository.dimension_run(run_id)
    if run is None:
        raise HTTPException(404, "Dimension score run not found")
    rows = repository.dimension_results(run_id, signal_id)
    if not rows:
        raise HTTPException(404, "Signal dimension scores not found")
    try:
        return dimension_score_payload(run, signal_id, rows)
    except InconsistentScoreSet as exc:
        raise HTTPException(409, str(exc)) from exc
