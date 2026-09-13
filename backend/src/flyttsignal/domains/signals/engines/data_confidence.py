"""Candidate policy for the reliability of identity and provenance inputs."""

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
class DataConfidenceParameters:
    strong_match_bonus: int = 20
    uncertain_match_penalty: int = -30
    complete_snapshot_bonus: int = 10
    incomplete_snapshot_penalty: int = -20
    unknown_snapshot_penalty: int = -40
    successful_run_bonus: int = 5
    failed_run_penalty: int = -20
    unit_identifier_present_bonus: int = 5
    stable_source_identity_bonus: int = 5
    missing_critical_field_penalty: int = -10


class DataConfidenceEngine(BaseScoreEngine):
    """Score data reliability without strengthening the underlying move hypothesis."""

    revision = "data-confidence/2026-09-02.property-reuse"

    def __init__(self, parameters: DataConfidenceParameters | None = None):
        self.parameters = parameters or DataConfidenceParameters()

    def evaluate(self, score_input: ScoreInput) -> ScoreResult:
        components: list[ScoreComponent] = []
        warnings: list[str] = []
        features = FeatureReader(score_input.snapshot, warnings)

        match = features.value("property_match")
        match_component = {
            "STRONG_MATCH": ("strong_property_match", self.parameters.strong_match_bonus),
            "UNCERTAIN_MATCH": (
                "uncertain_property_match",
                self.parameters.uncertain_match_penalty,
            ),
            "NO_MATCH": ("property_not_reused", 0),
        }.get(match)
        if match_component:
            components.append(
                ScoreComponent(
                    match_component[0],
                    match_component[1],
                    "No reusable property selected; source/address validity is not assessed"
                    if match == "NO_MATCH"
                    else f"Property reuse decision is {match}",
                )
            )
        else:
            components.append(
                ScoreComponent(
                    "unresolved_property_match",
                    self.parameters.uncertain_match_penalty,
                    "Property reuse decision is unavailable, conflicting, or unrecognized",
                )
            )
            warnings.append("property_match cannot establish identity certainty")
        if match == "UNCERTAIN_MATCH":
            warnings.append("property_match is uncertain_match")
        elif match == "NO_MATCH":
            warnings.append("property_match is no_match: no reused identity; validity not assessed")

        snapshot_status = features.value("snapshot_status")
        snapshot_component = {
            "COMPLETE": ("complete_snapshot", self.parameters.complete_snapshot_bonus),
            "INCOMPLETE": (
                "incomplete_snapshot",
                self.parameters.incomplete_snapshot_penalty,
            ),
            "UNKNOWN": ("unknown_snapshot", self.parameters.unknown_snapshot_penalty),
        }.get(snapshot_status)
        if snapshot_component:
            components.append(
                ScoreComponent(
                    snapshot_component[0],
                    snapshot_component[1],
                    f"Collection snapshot is {snapshot_status}",
                )
            )
        if snapshot_status in {"INCOMPLETE", "UNKNOWN"}:
            warnings.append(f"snapshot_status is {snapshot_status.lower()}")

        run_status = features.value("source_run_status")
        if run_status == "SUCCESS":
            components.append(
                ScoreComponent(
                    "successful_run",
                    self.parameters.successful_run_bonus,
                    "Collection run completed successfully",
                )
            )
        elif run_status is not None:
            components.append(
                ScoreComponent(
                    "unsuccessful_run",
                    self.parameters.failed_run_penalty,
                    f"Collection run is {run_status}",
                )
            )
            warnings.append(f"source_run_status is {str(run_status).lower()}")

        self._identity_components(features, components, warnings)
        self._critical_boolean(
            features, "coordinates_present", "Usable coordinates are missing", components, warnings
        )

        return ScoreResult(
            score=max(0, min(100, sum(component.points for component in components))),
            components=tuple(components),
            warnings=tuple(warnings),
            metadata={"dimension": ScoreDimension.DATA_CONFIDENCE.value},
        )

    def _identity_components(
        self,
        features: FeatureReader,
        components: list[ScoreComponent],
        warnings: list[str],
    ) -> None:
        unit_present = features.boolean("unit_identifier_present")
        if unit_present is True:
            components.append(
                ScoreComponent(
                    "unit_identifier_present",
                    self.parameters.unit_identifier_present_bonus,
                    "Publisher supplied a dwelling identifier",
                )
            )
        else:
            components.append(
                ScoreComponent(
                    "unit_identifier_missing",
                    self.parameters.missing_critical_field_penalty,
                    "Publisher omitted the dwelling identifier"
                    if unit_present is False
                    else "Dwelling identifier presence cannot be established",
                )
            )
            if unit_present is False:
                warnings.append("unit_identifier_present is false")

        for name in ("source_id", "source_item_id"):
            value = features.value(name)
            if value:
                components.append(
                    ScoreComponent(
                        f"stable_{name}",
                        self.parameters.stable_source_identity_bonus,
                        f"{name} is stable and tracked",
                    )
                )
            elif value is not None:
                warnings.append(f"{name} is empty")

    def _critical_boolean(
        self,
        features: FeatureReader,
        name: str,
        reason: str,
        components: list[ScoreComponent],
        warnings: list[str],
    ) -> None:
        value = features.boolean(name)
        if value is not True:
            components.append(
                ScoreComponent(
                    f"missing_{name}", self.parameters.missing_critical_field_penalty, reason
                )
            )
            warnings.append(f"{name} is not usable")


def calculate_data_confidence(
    snapshot: FeatureSnapshot,
    *,
    as_of: date,
    parameters: DataConfidenceParameters | None = None,
) -> ScoreResult:
    """Evaluate a real snapshot without inventing provenance or completeness."""

    return DataConfidenceEngine(parameters).evaluate(ScoreInput(snapshot=snapshot, as_of=as_of))
