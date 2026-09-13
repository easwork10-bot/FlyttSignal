"""Deterministic shadow evaluation of score dimensions against feature snapshots."""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from flyttsignal.domains.signals.engines.base import BaseScoreEngine, ScoreInput, ScoreResult
from flyttsignal.domains.signals.engines.data_confidence import (
    DataConfidenceEngine,
    DataConfidenceParameters,
)
from flyttsignal.domains.signals.engines.metadata import (
    DefinitionMetadata,
    ScoreDefinitionStatus,
    ScoreDimension,
)
from flyttsignal.domains.signals.engines.signal_strength import (
    SignalStrengthEngine,
    SignalStrengthParameters,
)
from flyttsignal.domains.signals.engines.timing import TimingEngine, TimingParameters
from flyttsignal.domains.signals.snapshots import FEATURE_SCHEMA_REVISION, FeatureSnapshot


@dataclass(frozen=True)
class EvaluationContext:
    """Caller-supplied values that make a shadow evaluation reproducible."""

    as_of: date
    definition_revision: str = "candidate"
    feature_schema_revision: str = FEATURE_SCHEMA_REVISION
    status: ScoreDefinitionStatus = ScoreDefinitionStatus.CANDIDATE


class ScoreEvaluationService:
    def definition(
        self,
        dimension: ScoreDimension,
        context: EvaluationContext,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[DefinitionMetadata, dict[str, Any]]:
        """Return the exact registered identity and typed parameters for one engine."""

        engine = self._engine(dimension, parameters)
        parameter_values = asdict(engine.parameters)
        metadata = DefinitionMetadata.from_parameters(
            definition_revision=context.definition_revision,
            parameters=parameter_values,
            feature_schema_revision=context.feature_schema_revision,
            engine_revision=engine.revision,
            as_of=context.as_of,
            dimension=dimension,
            status=context.status,
        )
        return metadata, parameter_values

    def evaluate_dimension(
        self,
        snapshot: FeatureSnapshot,
        dimension: ScoreDimension,
        context: EvaluationContext,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[ScoreResult, DefinitionMetadata]:
        self._validate(snapshot, context)
        metadata, _ = self.definition(dimension, context, parameters)
        engine = self._engine(dimension, parameters)
        result = engine.evaluate(ScoreInput(snapshot=snapshot, as_of=context.as_of))
        return result, metadata

    def evaluate_all_dimensions(
        self,
        snapshot: FeatureSnapshot,
        context: EvaluationContext,
        parameters: dict[ScoreDimension, dict[str, Any]] | None = None,
    ) -> dict[ScoreDimension, tuple[ScoreResult, DefinitionMetadata]]:
        return {
            dimension: self.evaluate_dimension(
                snapshot,
                dimension,
                context,
                parameters.get(dimension) if parameters else None,
            )
            for dimension in ScoreDimension
        }

    @staticmethod
    def _validate(snapshot: FeatureSnapshot, context: EvaluationContext) -> None:
        if snapshot.as_of_date != context.as_of:
            raise ValueError("evaluation as_of must equal snapshot as_of_date")
        if snapshot.schema_revision != context.feature_schema_revision:
            raise ValueError("evaluation feature schema must equal snapshot schema")

    @staticmethod
    def _engine(
        dimension: ScoreDimension, parameters: dict[str, Any] | None
    ) -> BaseScoreEngine:
        if dimension is ScoreDimension.SIGNAL_STRENGTH:
            return SignalStrengthEngine(
                SignalStrengthParameters(**parameters) if parameters else None
            )
        if dimension is ScoreDimension.DATA_CONFIDENCE:
            return DataConfidenceEngine(
                DataConfidenceParameters(**parameters) if parameters else None
            )
        if dimension is ScoreDimension.TIMING:
            return TimingEngine(TimingParameters(**parameters) if parameters else None)
        raise ValueError(f"unsupported score dimension: {dimension}")


def create_evaluation_context(*, as_of: date) -> EvaluationContext:
    """Create the default candidate context with an explicit evaluation date."""

    return EvaluationContext(as_of=as_of)
