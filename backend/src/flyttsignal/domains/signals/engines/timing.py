"""Candidate policy for when an observed housing change may matter."""

from dataclasses import dataclass
from datetime import date

from flyttsignal.domains.signals.engines.base import (
    BaseScoreEngine,
    ScoreComponent,
    ScoreInput,
    ScoreResult,
)
from flyttsignal.domains.signals.engines.feature_reader import FeatureReader
from flyttsignal.domains.signals.engines.metadata import ScoreDimension
from flyttsignal.domains.signals.snapshots import FeatureSnapshot


@dataclass(frozen=True)
class TimingParameters:
    ideal_lead_time_min_days: int = 30
    ideal_lead_time_max_days: int = 90
    ideal_lead_time_bonus: int = 20
    short_lead_time_bonus: int = 10
    long_lead_time_penalty: int = -10
    very_long_lead_time_penalty: int = -20
    immediate_move_bonus: int = 15
    near_future_move_bonus: int = 25
    medium_future_move_bonus: int = 15
    distant_future_move_penalty: int = -10
    past_move_penalty: int = -20
    fresh_signal_bonus: int = 10
    aging_signal_penalty: int = -5
    stale_signal_penalty: int = -15
    missing_date_penalty: int = -20


class TimingEngine(BaseScoreEngine):
    """Score timing separately from evidence strength and source confidence."""

    def __init__(self, parameters: TimingParameters | None = None):
        self.parameters = parameters or TimingParameters()

    def evaluate(self, score_input: ScoreInput) -> ScoreResult:
        components: list[ScoreComponent] = []
        warnings: list[str] = []
        features = FeatureReader(score_input.snapshot, warnings)

        lead_time = features.number("lead_time_days")
        if lead_time is not None:
            components.append(self._lead_time_component(lead_time))

        days_until = features.integer("days_until_available")
        if days_until is None:
            components.append(
                ScoreComponent(
                    "missing_available_date",
                    self.parameters.missing_date_penalty,
                    "Available date is unavailable or invalid",
                )
            )
        else:
            components.append(self._availability_component(days_until))

        age = features.integer("signal_age_days")
        if age is not None:
            components.append(self._age_component(age))

        listing_status = features.value("listing_status")
        misses = features.integer("consecutive_misses")
        if listing_status == "REMOVAL_CANDIDATE":
            warnings.append("listing is only a removal candidate; no urgency is inferred")
        elif listing_status == "REMOVED":
            components.append(
                ScoreComponent("listing_removed", -10, "Listing is removed, not a confirmed move")
            )
        if misses is not None and misses >= 2:
            components.append(
                ScoreComponent(
                    "consecutive_misses", -5 * misses, f"Listing missed {misses} snapshots"
                )
            )

        return ScoreResult(
            score=max(0, min(100, sum(component.points for component in components))),
            components=tuple(components),
            warnings=tuple(warnings),
            metadata={"dimension": ScoreDimension.TIMING.value},
        )

    def _lead_time_component(self, days: float) -> ScoreComponent:
        if days < 0:
            return ScoreComponent(
                "invalid_lead_time",
                self.parameters.past_move_penalty,
                f"Lead time {days:.1f} days is invalid",
            )
        if (
            self.parameters.ideal_lead_time_min_days
            <= days
            <= self.parameters.ideal_lead_time_max_days
        ):
            return ScoreComponent(
                "ideal_lead_time",
                self.parameters.ideal_lead_time_bonus,
                f"Lead time {days:.1f} days is in the ideal range",
            )
        if days < self.parameters.ideal_lead_time_min_days:
            return ScoreComponent(
                "short_lead_time",
                self.parameters.short_lead_time_bonus,
                f"Lead time {days:.1f} days is shorter than ideal",
            )
        if days > 180:
            return ScoreComponent(
                "very_long_lead_time",
                self.parameters.very_long_lead_time_penalty,
                f"Lead time {days:.1f} days is very long",
            )
        return ScoreComponent(
            "long_lead_time",
            self.parameters.long_lead_time_penalty,
            f"Lead time {days:.1f} days is longer than ideal",
        )

    def _availability_component(self, days: int) -> ScoreComponent:
        if days < 0:
            return ScoreComponent(
                "past_move",
                self.parameters.past_move_penalty,
                f"Window passed {abs(days)} days ago",
            )
        if days == 0:
            return ScoreComponent(
                "immediate_move", self.parameters.immediate_move_bonus, "Window is today"
            )
        if days <= 30:
            return ScoreComponent(
                "near_future_move",
                self.parameters.near_future_move_bonus,
                f"Window is {days} days away",
            )
        if days <= 90:
            return ScoreComponent(
                "medium_future_move",
                self.parameters.medium_future_move_bonus,
                f"Window is {days} days away",
            )
        return ScoreComponent(
            "distant_future_move",
            self.parameters.distant_future_move_penalty,
            f"Window is {days} days away",
        )

    def _age_component(self, age: int) -> ScoreComponent:
        if age <= 7:
            return ScoreComponent(
                "fresh_signal", self.parameters.fresh_signal_bonus, "Signal is fresh"
            )
        if age <= 30:
            return ScoreComponent(
                "aging_signal", self.parameters.aging_signal_penalty, f"Signal is {age} days old"
            )
        return ScoreComponent(
            "stale_signal", self.parameters.stale_signal_penalty, f"Signal is {age} days old"
        )


def calculate_timing(
    snapshot: FeatureSnapshot,
    *,
    as_of: date,
    parameters: TimingParameters | None = None,
) -> ScoreResult:
    """Evaluate a real snapshot without default dates or sentinel values."""

    return TimingEngine(parameters).evaluate(ScoreInput(snapshot=snapshot, as_of=as_of))
