import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.signals import signal_out
from flyttsignal.api.schemas.signals import SignalList, SignalOut
from flyttsignal.db.repositories.dashboard import ACTIVE_SCORE_SCOPE, DashboardRepository
from flyttsignal.db.repositories.score_activations import ScoreActivationRepository
from flyttsignal.db.repositories.signal_timing import SignalTimingRepository

router = APIRouter()


@router.get("/signals", response_model=SignalList, operation_id="listSignals")
def list_signals(
    db: Db,
    city_id: int | None = None,
    min_strength: Annotated[int, Query(ge=0, le=100)] = 0,
    signal_type: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    found = DashboardRepository(db).signals(
        city_id=city_id,
        min_strength=min_strength,
        signal_type=signal_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    dimensions = ScoreActivationRepository(db).active_signal_dimensions(
        scope_key=ACTIVE_SCORE_SCOPE,
        city_id=city_id or 1,
        signal_ids={item.id for item in found},
    )
    if len(dimensions) != len(found):
        raise HTTPException(409, "Active dimension scores are incomplete")
    timing = SignalTimingRepository(db).current_for_signals(
        {item.id: item.signal_type for item in found}
    )
    return SignalList(
        items=[
            signal_out(item, dimensions[item.id], timing=timing[item.id])
            for item in found
        ],
        count=len(found),
    )


@router.get("/signals/{signal_id}", response_model=SignalOut, operation_id="getSignal")
def get_signal(signal_id: uuid.UUID, db: Db):
    found = DashboardRepository(db).signal(signal_id)
    if found is None:
        raise HTTPException(404, "Signal not found")
    dimensions = ScoreActivationRepository(db).active_signal_dimensions(
        scope_key=ACTIVE_SCORE_SCOPE,
        city_id=found.property.address.city_id,
        signal_ids={found.id},
    )
    if found.id not in dimensions:
        raise HTTPException(409, "Active dimension scores are incomplete")
    timing = SignalTimingRepository(db).current_for_signals(
        {found.id: found.signal_type}
    )
    return signal_out(
        found,
        dimensions[found.id],
        detail=True,
        timing=timing[found.id],
    )
