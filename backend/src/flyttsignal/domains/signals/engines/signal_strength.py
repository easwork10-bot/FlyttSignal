"""Candidate policy for the strength of evidence that a housing change exists."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

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
class SignalStrengthParameters:
    base_rental_listed_points: int = 30
    base_new_build_move_in_points: int = 35
    base_sale_sold_points: int = 40
    known_effective_date_points: int = 20
    within_30_days_points: int = 20
    within_60_days_points: int = 15
    within_120_days_points: int = 5
    effective_date_passed_penalty: int = -10
    independent_source_points: int = 10
    stale_evidence_90_days_penalty: int = -20
    stale_evidence_30_days_penalty: int = -10


class SignalStrengthEngine(BaseScoreEngine):
    """Use event semantics, dates, observation freshness, and independent evidence only."""

    def __init__(self, parameters: SignalStrengthParameters | None = None):
        self.parameters = parameters or SignalStrengthParameters()

    def evaluate(self, score_input: ScoreInput) -> ScoreResult:
        components: list[ScoreComponent] = []
        warnings: list[str] = []
        features = FeatureReader(score_input.snapshot, warnings)

        event_type = features.value("event_type")
        base_score = self._base_score(event_type)
        if base_score:
            components.append(
                ScoreComponent("event_type_base", base_score, f"Base evidence for {event_type}")
            )

        available_from = features.value("available_from")
        if isinstance(available_from, date):
            components.append(
                ScoreComponent(
                    "known_effective_date",
                    self.parameters.known_effective_date_points,
                    "Advertised effective date is known",
                )
            )
            days = features.integer("days_until_available")
            if days is not None:
                component = self._date_component(days)
                if component:
                    components.append(component)
        elif available_from is not None:
            warnings.append("available_from is not a date")

        independent_count = features.integer("independent_evidence_count")
        if independent_count is not None and independent_count >= 2:
            components.append(
                ScoreComponent(
                    "independent_source",
                    self.parameters.independent_source_points,
                    "A second independently proven source corroborates the observation",
                )
            )

        last_seen = features.value("last_seen_at")
        age = self._observation_age_days(last_seen, score_input.as_of, warnings)
        if age is not None and age > 90:
            components.append(
                ScoreComponent(
                    "stale_evidence",
                    self.parameters.stale_evidence_90_days_penalty,
                    "Observation has not refreshed for more than 90 days",
                )
            )
        elif age is not None and age > 30:
            components.append(
                ScoreComponent(
                    "aging_evidence",
                    self.parameters.stale_evidence_30_days_penalty,
                    "Observation has not refreshed for more than 30 days",
                )
            )

        return ScoreResult(
            score=_bounded_sum(components),
            components=tuple(components),
            warnings=tuple(warnings),
            metadata={"dimension": ScoreDimension.SIGNAL_STRENGTH.value},
        )

    def _base_score(self, event_type: object) -> int:
        return {
            "RENTAL_LISTED": self.parameters.base_rental_listed_points,
            "NEW_BUILD_MOVE_IN": self.parameters.base_new_build_move_in_points,
            "SALE_SOLD": self.parameters.base_sale_sold_points,
        }.get(event_type, 0)

    def _date_component(self, days: int) -> ScoreComponent | None:
        if days < 0:
            return ScoreComponent(
                "effective_date_passed",
                self.parameters.effective_date_passed_penalty,
                f"Effective date passed {abs(days)} days ago",
            )
        if days <= 30:
            return ScoreComponent(
                "within_30_days", self.parameters.within_30_days_points, "Window is 0–30 days"
            )
        if days <= 60:
            return ScoreComponent(
                "within_60_days", self.parameters.within_60_days_points, "Window is 31–60 days"
            )
        if days <= 120:
            return ScoreComponent(
                "within_120_days", self.parameters.within_120_days_points, "Window is 61–120 days"
            )
        return None

    @staticmethod
    def _observation_age_days(
        value: object, as_of: date, warnings: list[str]
    ) -> int | None:
        if isinstance(value, datetime):
            observed_date = value.astimezone(UTC).date() if value.tzinfo else value.date()
        elif isinstance(value, date):
            observed_date = value
        elif value is None:
            return None
        else:
            warnings.append("last_seen_at is not a date or datetime")
            return None
        return (as_of - observed_date).days


def _bounded_sum(components: list[ScoreComponent]) -> int:
    return max(0, min(100, sum(component.points for component in components)))


def calculate_signal_strength(
    snapshot: FeatureSnapshot,
    *,
    as_of: date,
    parameters: SignalStrengthParameters | None = None,
) -> ScoreResult:
    """Evaluate a real snapshot without fabricating missing inputs."""

    return SignalStrengthEngine(parameters).evaluate(ScoreInput(snapshot=snapshot, as_of=as_of))
