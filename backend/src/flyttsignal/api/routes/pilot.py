import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.pilot import pilot_signal_out
from flyttsignal.api.schemas.pilot import (
    PilotActivityRecordedOut,
    PilotActivityUpsert,
    PilotCohortCriteriaOut,
    PilotContextIn,
    PilotFeedbackOut,
    PilotFeedbackUpsert,
    PilotMetricsOut,
    PilotPaginationOut,
    PilotSignalFiltersOut,
    PilotSignalListOut,
    PilotSignalSummaryOut,
)
from flyttsignal.db.models import Signal
from flyttsignal.db.repositories.dashboard import DashboardRepository
from flyttsignal.db.repositories.pilot_activity import PilotActivityRepository
from flyttsignal.db.repositories.pilot_feedback import PilotFeedbackRepository
from flyttsignal.db.repositories.score_activations import (
    ActiveDimensionContext,
    ActiveSignalDimensions,
    ScoreActivationRepository,
)
from flyttsignal.db.repositories.signal_timing import SignalTimingRepository
from flyttsignal.domains.signals.pilot import (
    PILOT_COHORT_VERSION,
    PilotCohortPolicy,
    PilotReviewStatus,
    PilotSignalFilters,
    PilotSignalSort,
)

router = APIRouter()


def _pilot_policy(context: PilotContextIn) -> PilotCohortPolicy:
    policy = PilotCohortPolicy()
    if (
        context.cohort_version != PILOT_COHORT_VERSION
        or context.dimension_scope_key != policy.dimension_scope_key
    ):
        raise HTTPException(422, "Unsupported pilot cohort or dimension scope")
    return policy


def _active_dimension_context(db, policy: PilotCohortPolicy) -> ActiveDimensionContext:
    try:
        return ScoreActivationRepository(db).active_dimension_context(
            scope_key=policy.dimension_scope_key,
            city_id=policy.city_id,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


def _validated_dimension_context(db, context: PilotContextIn) -> ActiveDimensionContext:
    active = _active_dimension_context(db, _pilot_policy(context))
    if (
        context.score_run_id != active.run_id
        or context.score_as_of_date != active.as_of_date
        or context.definition_set_hash != active.definition_set_hash
    ):
        raise HTTPException(409, "Pilot context no longer matches the active dimension run")
    return active


def _pilot_signals_for_context(
    db,
    context: PilotContextIn,
    signal_ids: set[uuid.UUID],
) -> tuple[list[Signal], dict[uuid.UUID, ActiveSignalDimensions], ActiveDimensionContext]:
    policy = _pilot_policy(context)
    active_context = _validated_dimension_context(db, context)
    signals = list(
        db.scalars(
            DashboardRepository(db)
            .pilot_signal_query(
                policy=policy,
                as_of=context.cohort_as_of_date,
                score_run_id=active_context.run_id,
            )
            .where(Signal.id.in_(signal_ids))
        ).unique()
    )
    if {signal.id for signal in signals} != signal_ids:
        raise HTTPException(404, "One or more signals are outside the referenced pilot cohort")
    dimensions = ScoreActivationRepository(db).active_signal_dimensions(
        scope_key=active_context.scope_key,
        city_id=policy.city_id,
        signal_ids=signal_ids,
    )
    if set(dimensions) != signal_ids:
        raise HTTPException(409, "Active dimension scores are incomplete")
    return signals, dimensions, active_context


@router.get(
    "/pilot/signals",
    response_model=PilotSignalListOut,
    operation_id="listPilotSignals",
)
def list_pilot_signals(
    db: Db,
    as_of: date | None = None,
    address_query: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    pilot_key: Annotated[
        str | None,
        Query(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]+$"),
    ] = None,
    review_status: PilotReviewStatus = "ALL",
    strength_band: Literal["LOW", "MEDIUM", "HIGH"] | None = None,
    signal_type: str | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    property_type: str | None = None,
    min_rooms: Annotated[Decimal | None, Query(ge=0)] = None,
    max_rooms: Annotated[Decimal | None, Query(ge=0)] = None,
    min_area_m2: Annotated[Decimal | None, Query(ge=0)] = None,
    max_area_m2: Annotated[Decimal | None, Query(ge=0)] = None,
    center_latitude: Annotated[Decimal | None, Query(ge=-90, le=90)] = None,
    center_longitude: Annotated[Decimal | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[Decimal | None, Query(gt=0, le=100)] = None,
    sort: PilotSignalSort = "PRIORITY",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    effective_date = as_of or date.today()
    policy = PilotCohortPolicy()
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "from must be on or before to")
    if min_rooms is not None and max_rooms is not None and min_rooms > max_rooms:
        raise HTTPException(422, "min_rooms must not exceed max_rooms")
    if min_area_m2 is not None and max_area_m2 is not None and min_area_m2 > max_area_m2:
        raise HTTPException(422, "min_area_m2 must not exceed max_area_m2")
    radius_parts = (center_latitude, center_longitude, radius_km)
    if any(value is not None for value in radius_parts) and not all(
        value is not None for value in radius_parts
    ):
        raise HTTPException(
            422, "center_latitude, center_longitude and radius_km are required together"
        )
    if review_status != "ALL" and not pilot_key:
        raise HTTPException(422, "pilot_key is required when review_status is filtered")
    normalized_address_query = (
        " ".join(address_query.split()) if address_query is not None else None
    )
    if address_query is not None and len(normalized_address_query or "") < 2:
        raise HTTPException(422, "address_query must contain at least two visible characters")
    active_context = _active_dimension_context(db, policy)
    filters = PilotSignalFilters(
        address_query=normalized_address_query,
        review_status=review_status,
        strength_band=strength_band,
        signal_type=signal_type,
        date_from=date_from,
        date_to=date_to,
        property_type=property_type,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        min_area_m2=min_area_m2,
        max_area_m2=max_area_m2,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        radius_km=radius_km,
    )
    signals, summary = DashboardRepository(db).pilot_signals(
        policy=policy,
        as_of=effective_date,
        score_run_id=active_context.run_id,
        filters=filters,
        pilot_key=pilot_key,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    activation_repository = ScoreActivationRepository(db)
    dimensions = activation_repository.active_signal_dimensions(
        scope_key=policy.dimension_scope_key,
        city_id=policy.city_id,
        signal_ids={signal.id for signal in signals},
    )
    if len(dimensions) != len(signals):
        raise HTTPException(409, "Active dimension scores are incomplete")
    timings = SignalTimingRepository(db).current_for_signals(
        {signal.id: signal.signal_type for signal in signals}
    )
    feedback = (
        PilotFeedbackRepository(db).feedback_by_signal_ids(
            signal_ids={signal.id for signal in signals},
            pilot_key=pilot_key,
            cohort_version=policy.cohort_version,
            dimension_context=active_context,
            cohort_as_of_date=effective_date,
        )
        if pilot_key
        else {}
    )
    items = [
        pilot_signal_out(
            signal,
            dimensions[signal.id],
            as_of=effective_date,
            timing=timings[signal.id],
            feedback=feedback.get(signal.id),
        )
        for signal in signals
    ]
    return PilotSignalListOut(
        cohort_version=policy.cohort_version,
        cohort_as_of_date=effective_date,
        dimension_scope_key=active_context.scope_key,
        score_run_id=active_context.run_id,
        score_as_of_date=active_context.as_of_date,
        definition_set_hash=active_context.definition_set_hash,
        criteria=PilotCohortCriteriaOut(
            city_id=policy.city_id,
            signal_age_days=policy.signal_age_days,
            move_horizon_days=policy.move_horizon_days,
            dated_signals_only=True,
        ),
        applied_filters=PilotSignalFiltersOut(**filters.__dict__),
        sort=sort,
        summary=PilotSignalSummaryOut(**summary.__dict__),
        pagination=PilotPaginationOut(
            limit=limit,
            offset=offset,
            has_previous=offset > 0,
            has_next=offset + len(signals) < summary.total,
        ),
        items=items,
        count=len(items),
        total=summary.total,
    )


@router.get(
    "/pilot/signals/{signal_id}/feedback",
    response_model=PilotFeedbackOut | None,
    operation_id="getPilotSignalFeedback",
)
def get_pilot_signal_feedback(
    signal_id: uuid.UUID,
    db: Db,
    pilot_key: Annotated[
        str,
        Query(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]+$"),
    ],
    cohort_version: str,
    cohort_as_of_date: date,
    dimension_scope_key: str,
    score_run_id: uuid.UUID,
    score_as_of_date: date,
    definition_set_hash: str,
):
    context = PilotContextIn(
        pilot_key=pilot_key,
        cohort_version=cohort_version,
        cohort_as_of_date=cohort_as_of_date,
        dimension_scope_key=dimension_scope_key,
        score_run_id=score_run_id,
        score_as_of_date=score_as_of_date,
        definition_set_hash=definition_set_hash,
    )
    active_context = _validated_dimension_context(db, context)
    return PilotFeedbackRepository(db).feedback(
        signal_id=signal_id,
        pilot_key=pilot_key,
        cohort_version=cohort_version,
        dimension_context=active_context,
        cohort_as_of_date=cohort_as_of_date,
    )


@router.put(
    "/pilot/signals/{signal_id}/feedback",
    response_model=PilotFeedbackOut,
    operation_id="upsertPilotSignalFeedback",
)
def upsert_pilot_signal_feedback(
    signal_id: uuid.UUID,
    payload: PilotFeedbackUpsert,
    db: Db,
):
    signals, dimensions, active_context = _pilot_signals_for_context(db, payload, {signal_id})
    signal = signals[0]
    feedback = PilotFeedbackRepository(db).upsert(
        signal=signal,
        dimensions=dimensions[signal_id],
        pilot_key=payload.pilot_key,
        cohort_version=payload.cohort_version,
        dimension_context=active_context,
        cohort_as_of_date=payload.cohort_as_of_date,
        verdict=payload.verdict,
        reason=payload.reason,
        note=payload.note,
    )
    db.commit()
    db.refresh(feedback)
    return feedback


@router.put(
    "/pilot/activity",
    response_model=PilotActivityRecordedOut,
    operation_id="recordPilotActivity",
)
def record_pilot_activity(payload: PilotActivityUpsert, db: Db):
    signal_ids = set(payload.signal_ids)
    _, dimensions, active_context = _pilot_signals_for_context(db, payload, signal_ids)
    recorded_count = PilotActivityRepository(db).record(
        signal_ids=signal_ids,
        dimensions=dimensions,
        pilot_key=payload.pilot_key,
        cohort_version=payload.cohort_version,
        dimension_context=active_context,
        cohort_as_of_date=payload.cohort_as_of_date,
        activity_type=payload.activity_type,
    )
    db.commit()
    return PilotActivityRecordedOut(
        activity_type=payload.activity_type,
        recorded_count=recorded_count,
    )


@router.get(
    "/pilot/metrics",
    response_model=PilotMetricsOut,
    operation_id="getPilotMetrics",
)
def get_pilot_metrics(
    db: Db,
    pilot_key: Annotated[
        str,
        Query(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]+$"),
    ],
    cohort_version: str,
    cohort_as_of_date: date,
    dimension_scope_key: str,
    score_run_id: uuid.UUID,
    score_as_of_date: date,
    definition_set_hash: str,
):
    context = PilotContextIn(
        pilot_key=pilot_key,
        cohort_version=cohort_version,
        cohort_as_of_date=cohort_as_of_date,
        dimension_scope_key=dimension_scope_key,
        score_run_id=score_run_id,
        score_as_of_date=score_as_of_date,
        definition_set_hash=definition_set_hash,
    )
    active_context = _validated_dimension_context(db, context)
    activities, verdicts, reasons = PilotActivityRepository(db).metrics(
        pilot_key=pilot_key,
        cohort_version=cohort_version,
        dimension_context=active_context,
        cohort_as_of_date=cohort_as_of_date,
    )
    shown = activities.get("SHOWN", 0)
    opened = activities.get("OPENED", 0)
    useful = verdicts.get("USEFUL", 0)
    maybe = verdicts.get("MAYBE", 0)
    not_useful = verdicts.get("NOT_USEFUL", 0)
    reviewed = useful + maybe + not_useful
    return PilotMetricsOut(
        **context.model_dump(),
        shown=shown,
        opened=opened,
        reviewed=reviewed,
        useful=useful,
        maybe=maybe,
        not_useful=not_useful,
        open_rate=opened / shown if shown else None,
        review_rate=reviewed / opened if opened else None,
        useful_rate=useful / reviewed if reviewed else None,
        reason_counts=dict(sorted(reasons.items())),
    )
