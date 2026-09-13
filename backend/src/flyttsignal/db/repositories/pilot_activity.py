import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from flyttsignal.db.models import PilotSignalActivity, PilotSignalFeedback
from flyttsignal.db.repositories.score_activations import (
    ActiveDimensionContext,
    ActiveSignalDimensions,
)
from flyttsignal.domains.pilot.activity import PilotActivityType


class PilotActivityRepository:
    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        *,
        signal_ids: set[uuid.UUID],
        dimensions: dict[uuid.UUID, ActiveSignalDimensions],
        pilot_key: str,
        cohort_version: str,
        dimension_context: ActiveDimensionContext,
        cohort_as_of_date: date,
        activity_type: PilotActivityType,
    ) -> int:
        occurred_at = datetime.now(UTC)
        statement = insert(PilotSignalActivity).values(
            [
                {
                    "signal_id": signal_id,
                    "pilot_key": pilot_key,
                    "cohort_version": cohort_version,
                    "cohort_as_of_date": cohort_as_of_date,
                    "dimension_scope_key": dimension_context.scope_key,
                    "score_run_id": dimension_context.run_id,
                    "score_as_of_date": dimension_context.as_of_date,
                    "definition_set_hash": dimension_context.definition_set_hash,
                    "signal_strength_at_activity": dimensions[signal_id].signal_strength,
                    "data_confidence_at_activity": dimensions[signal_id].data_confidence,
                    "timing_at_activity": dimensions[signal_id].timing,
                    "activity_type": activity_type.value,
                    "occurrence_count": 1,
                    "last_occurred_at": occurred_at,
                }
                for signal_id in signal_ids
            ]
        )
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    PilotSignalActivity.pilot_key,
                    PilotSignalActivity.signal_id,
                    PilotSignalActivity.cohort_version,
                    PilotSignalActivity.dimension_scope_key,
                    PilotSignalActivity.score_run_id,
                    PilotSignalActivity.cohort_as_of_date,
                    PilotSignalActivity.activity_type,
                ],
                set_={
                    "occurrence_count": PilotSignalActivity.occurrence_count + 1,
                    "last_occurred_at": occurred_at,
                },
            )
        )
        return len(signal_ids)

    def metrics(
        self,
        *,
        pilot_key: str,
        cohort_version: str,
        dimension_context: ActiveDimensionContext,
        cohort_as_of_date: date,
    ) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
        activity_counts = dict(
            self.session.execute(
                select(PilotSignalActivity.activity_type, func.count())
                .where(
                    PilotSignalActivity.pilot_key == pilot_key,
                    PilotSignalActivity.cohort_version == cohort_version,
                    PilotSignalActivity.dimension_scope_key == dimension_context.scope_key,
                    PilotSignalActivity.score_run_id == dimension_context.run_id,
                    PilotSignalActivity.cohort_as_of_date == cohort_as_of_date,
                )
                .group_by(PilotSignalActivity.activity_type)
            ).all()
        )
        verdict_counts = dict(
            self.session.execute(
                select(PilotSignalFeedback.verdict, func.count())
                .where(
                    PilotSignalFeedback.pilot_key == pilot_key,
                    PilotSignalFeedback.cohort_version == cohort_version,
                    PilotSignalFeedback.dimension_scope_key == dimension_context.scope_key,
                    PilotSignalFeedback.score_run_id == dimension_context.run_id,
                    PilotSignalFeedback.cohort_as_of_date == cohort_as_of_date,
                )
                .group_by(PilotSignalFeedback.verdict)
            ).all()
        )
        reason_counts = dict(
            self.session.execute(
                select(PilotSignalFeedback.reason, func.count())
                .where(
                    PilotSignalFeedback.pilot_key == pilot_key,
                    PilotSignalFeedback.cohort_version == cohort_version,
                    PilotSignalFeedback.dimension_scope_key == dimension_context.scope_key,
                    PilotSignalFeedback.score_run_id == dimension_context.run_id,
                    PilotSignalFeedback.cohort_as_of_date == cohort_as_of_date,
                )
                .group_by(PilotSignalFeedback.reason)
            ).all()
        )
        return activity_counts, verdict_counts, reason_counts
