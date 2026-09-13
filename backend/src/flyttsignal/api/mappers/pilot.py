from datetime import date

from flyttsignal.api.mappers.signals import signal_out
from flyttsignal.api.schemas.pilot import PilotSignalFeedbackSummaryOut, PilotSignalOut
from flyttsignal.db.models import PilotSignalFeedback, Signal
from flyttsignal.db.repositories.score_activations import ActiveSignalDimensions
from flyttsignal.domains.signals.pilot import (
    days_until_window_start,
    signal_age_days,
    strength_band,
)
from flyttsignal.domains.signals.resolved_timing import ResolvedSignalTiming
from flyttsignal.domains.signals.timing import TimingState


def pilot_signal_out(
    signal: Signal,
    dimensions: ActiveSignalDimensions,
    *,
    as_of: date,
    timing: ResolvedSignalTiming,
    feedback: PilotSignalFeedback | None = None,
) -> PilotSignalOut:
    if timing.primary.state != TimingState.PRESENT or timing.primary.value is None:
        raise ValueError("pilot signal requires advertised available-from timing")
    return PilotSignalOut(
        **signal_out(signal, dimensions, detail=True, timing=timing).model_dump(),
        strength_band=strength_band(dimensions.signal_strength),
        signal_age_days=signal_age_days(signal.created_at, as_of),
        days_until_window_start=days_until_window_start(timing.primary.value, as_of),
        pilot_feedback=(
            PilotSignalFeedbackSummaryOut(
                verdict=feedback.verdict,
                reason=feedback.reason,
                reviewed_at=feedback.reviewed_at,
            )
            if feedback
            else None
        ),
    )
