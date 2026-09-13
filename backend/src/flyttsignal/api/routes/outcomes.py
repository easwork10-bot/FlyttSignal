import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.outcomes import (
    OutcomeSummaryItem,
    OutcomeSummaryOut,
    SignalOutcomeOut,
)
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/signals/{signal_id}/outcomes",
    response_model=list[SignalOutcomeOut],
    operation_id="listSignalOutcomes",
)
def list_signal_outcomes(signal_id: uuid.UUID, db: Db):
    repository = DashboardRepository(db)
    if repository.signal(signal_id) is None:
        raise HTTPException(404, "Signal not found")
    return repository.signal_outcomes(signal_id)


@router.get(
    "/outcomes/summary",
    response_model=OutcomeSummaryOut,
    operation_id="getOutcomeSummary",
)
def get_outcome_summary(db: Db):
    population_count, outcomes = DashboardRepository(db).signal_outcome_population()
    grouped: dict[tuple[str, str, str], int] = {}
    for outcome in outcomes:
        key = (outcome.outcome_type, outcome.subject, outcome.verification_level)
        grouped[key] = grouped.get(key, 0) + 1
    return OutcomeSummaryOut(
        generated_at=datetime.now(UTC),
        signal_population_count=population_count,
        signals_with_outcomes=len({outcome.signal_id for outcome in outcomes}),
        outcome_count=len(outcomes),
        confirmed_move_count=sum(
            outcome.outcome_type == "CONFIRMED_MOVE"
            and outcome.subject == "HOUSEHOLD_MOVE"
            and outcome.verification_level == "CONFIRMED"
            for outcome in outcomes
        ),
        items=[
            OutcomeSummaryItem(
                outcome_type=outcome_type,
                subject=subject,
                verification_level=verification_level,
                count=count,
            )
            for (outcome_type, subject, verification_level), count in sorted(grouped.items())
        ],
    )
