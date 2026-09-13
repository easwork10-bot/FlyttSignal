import uuid

from fastapi import APIRouter, HTTPException

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.score_activations import ScoreActivationSetOut
from flyttsignal.api.schemas.score_runs import SignalDimensionSetOut
from flyttsignal.db.repositories.score_activations import ScoreActivationRepository
from flyttsignal.db.repositories.score_runs import ScoreRunRepository
from flyttsignal.scoring.read_models import (
    InconsistentScoreSet,
    activation_payload,
    active_dimension_score_payload,
)

router = APIRouter()


@router.get(
    "/score-activations/{scope_key}",
    response_model=ScoreActivationSetOut,
    operation_id="getScoreActivationSet",
)
def get_score_activation_set(scope_key: str, db: Db, city_id: int = 1):
    rows = ScoreActivationRepository(db).active_score_activations(
        scope_key=scope_key,
        city_id=city_id,
    )
    if not rows:
        raise HTTPException(404, "Active score scope not found")
    try:
        return activation_payload(rows, scope_key=scope_key, city_id=city_id)
    except InconsistentScoreSet as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/score-activations/{scope_key}/signals/{signal_id}",
    response_model=SignalDimensionSetOut,
    operation_id="getActiveSignalDimensions",
)
def get_active_signal_dimensions(
    scope_key: str, signal_id: uuid.UUID, db: Db, city_id: int = 1
):
    activations = ScoreActivationRepository(db).active_score_activations(
        scope_key=scope_key,
        city_id=city_id,
    )
    if not activations:
        raise HTTPException(404, "Active score scope not found")
    run = activations[0][2]
    rows = ScoreRunRepository(db).dimension_results(run.id, signal_id)
    if not rows:
        raise HTTPException(404, "Signal dimension scores not found")
    try:
        return active_dimension_score_payload(
            activations,
            rows,
            scope_key=scope_key,
            city_id=city_id,
            signal_id=signal_id,
        )
    except InconsistentScoreSet as exc:
        raise HTTPException(409, str(exc)) from exc
