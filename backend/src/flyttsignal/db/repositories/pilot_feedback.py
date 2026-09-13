import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import PilotSignalFeedback, Signal
from flyttsignal.db.repositories.score_activations import (
    ActiveDimensionContext,
    ActiveSignalDimensions,
)
from flyttsignal.domains.pilot.feedback import PilotFeedbackReason, PilotFeedbackVerdict


class PilotFeedbackRepository:
    def __init__(self, session: Session):
        self.session = session

    def feedback(
        self,
        *,
        signal_id: uuid.UUID,
        pilot_key: str,
        cohort_version: str,
        dimension_context: ActiveDimensionContext,
        cohort_as_of_date: date,
    ) -> PilotSignalFeedback | None:
        return self.session.scalar(
            select(PilotSignalFeedback).where(
                PilotSignalFeedback.signal_id == signal_id,
                PilotSignalFeedback.pilot_key == pilot_key,
                PilotSignalFeedback.cohort_version == cohort_version,
                PilotSignalFeedback.dimension_scope_key == dimension_context.scope_key,
                PilotSignalFeedback.score_run_id == dimension_context.run_id,
                PilotSignalFeedback.cohort_as_of_date == cohort_as_of_date,
            )
        )

    def feedback_by_signal_ids(
        self,
        *,
        signal_ids: set[uuid.UUID],
        pilot_key: str,
        cohort_version: str,
        dimension_context: ActiveDimensionContext,
        cohort_as_of_date: date,
    ) -> dict[uuid.UUID, PilotSignalFeedback]:
        if not signal_ids:
            return {}
        feedback = self.session.scalars(
            select(PilotSignalFeedback).where(
                PilotSignalFeedback.signal_id.in_(signal_ids),
                PilotSignalFeedback.pilot_key == pilot_key,
                PilotSignalFeedback.cohort_version == cohort_version,
                PilotSignalFeedback.dimension_scope_key == dimension_context.scope_key,
                PilotSignalFeedback.score_run_id == dimension_context.run_id,
                PilotSignalFeedback.cohort_as_of_date == cohort_as_of_date,
            )
        )
        return {item.signal_id: item for item in feedback}

    def upsert(
        self,
        *,
        signal: Signal,
        dimensions: ActiveSignalDimensions,
        pilot_key: str,
        cohort_version: str,
        dimension_context: ActiveDimensionContext,
        cohort_as_of_date: date,
        verdict: PilotFeedbackVerdict,
        reason: PilotFeedbackReason,
        note: str | None,
    ) -> PilotSignalFeedback:
        feedback = self.feedback(
            signal_id=signal.id,
            pilot_key=pilot_key,
            cohort_version=cohort_version,
            dimension_context=dimension_context,
            cohort_as_of_date=cohort_as_of_date,
        )
        if feedback is None:
            feedback = PilotSignalFeedback(
                signal_id=signal.id,
                pilot_key=pilot_key,
                cohort_version=cohort_version,
                cohort_as_of_date=cohort_as_of_date,
                dimension_scope_key=dimension_context.scope_key,
                score_run_id=dimension_context.run_id,
                score_as_of_date=dimension_context.as_of_date,
                definition_set_hash=dimension_context.definition_set_hash,
            )
            self.session.add(feedback)
        feedback.signal_strength_at_review = dimensions.signal_strength
        feedback.data_confidence_at_review = dimensions.data_confidence
        feedback.timing_at_review = dimensions.timing
        feedback.verdict = verdict.value
        feedback.reason = reason.value
        feedback.note = note
        self.session.flush()
        return feedback
