import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    ScoreActivation,
    ScoreDefinition,
    ScoreRun,
    SignalDimensionEvaluation,
)
from flyttsignal.domains.signals.engines.metadata import ScoreDimension


@dataclass(frozen=True)
class ScoreActivationResult:
    scope_type: str
    scope_key: str
    city_id: int
    decision_run_id: uuid.UUID
    definition_ids: dict[str, uuid.UUID]
    created: bool


@dataclass(frozen=True)
class ActiveSignalDimensions:
    signal_id: uuid.UUID
    run_id: uuid.UUID
    as_of_date: date
    definition_set_hash: str
    signal_strength: int
    data_confidence: int
    timing: int


@dataclass(frozen=True)
class ActiveDimensionContext:
    scope_key: str
    city_id: int
    run_id: uuid.UUID
    as_of_date: date
    definition_set_hash: str


def active_dimensions_subquery(*, scope_key: str, city_id: int):
    """Return complete activated dimension sets; incomplete signals fail closed."""

    return (
        select(
            SignalDimensionEvaluation.signal_id.label("signal_id"),
            ScoreRun.id.label("run_id"),
            ScoreRun.as_of_date.label("as_of_date"),
            ScoreRun.definition_set_hash.label("definition_set_hash"),
            func.max(
                case(
                    (
                        SignalDimensionEvaluation.dimension == "SIGNAL_STRENGTH",
                        SignalDimensionEvaluation.score,
                    )
                )
            ).label("signal_strength"),
            func.max(
                case(
                    (
                        SignalDimensionEvaluation.dimension == "DATA_CONFIDENCE",
                        SignalDimensionEvaluation.score,
                    )
                )
            ).label("data_confidence"),
            func.max(
                case(
                    (
                        SignalDimensionEvaluation.dimension == "TIMING",
                        SignalDimensionEvaluation.score,
                    )
                )
            ).label("timing"),
        )
        .join(
            ScoreActivation,
            (ScoreActivation.decision_run_id == SignalDimensionEvaluation.run_id)
            & (ScoreActivation.definition_id == SignalDimensionEvaluation.definition_id)
            & (ScoreActivation.dimension == SignalDimensionEvaluation.dimension),
        )
        .join(ScoreRun, ScoreRun.id == SignalDimensionEvaluation.run_id)
        .where(
            ScoreActivation.scope_key == scope_key,
            ScoreActivation.city_id == city_id,
            ScoreActivation.scope_type == "INTERNAL_PILOT",
            ScoreActivation.retired_at.is_(None),
        )
        .group_by(
            SignalDimensionEvaluation.signal_id,
            ScoreRun.id,
            ScoreRun.as_of_date,
            ScoreRun.definition_set_hash,
        )
        .having(func.count(func.distinct(SignalDimensionEvaluation.dimension)) == 3)
        .subquery("active_signal_dimensions")
    )


class ScoreActivationRepository:
    def __init__(self, session: Session):
        self.session = session

    def activate_dimension_run(
        self,
        *,
        run_id: uuid.UUID,
        city_id: int,
        scope_key: str,
        decision_reason: str,
        apply: bool,
    ) -> ScoreActivationResult:
        """Select one complete run for an internal pilot scope, optionally persisting it."""

        scope_key = scope_key.strip()
        decision_reason = decision_reason.strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", scope_key):
            raise ValueError("scope_key must be a lowercase kebab-case identifier")
        if len(decision_reason) < 40:
            raise ValueError("activation requires a substantive decision reason")
        run = self.session.get(ScoreRun, run_id)
        if run is None or run.status != "COMPLETE":
            raise ValueError("activation requires one complete score run")
        if run.city_id != city_id:
            raise ValueError("activation city does not match the score run")

        definition_ids = self._validated_run_definitions(run)
        existing = list(
            self.session.scalars(
                select(ScoreActivation)
                .where(
                    ScoreActivation.scope_key == scope_key,
                    ScoreActivation.city_id == city_id,
                    ScoreActivation.retired_at.is_(None),
                )
                .order_by(ScoreActivation.dimension)
            )
        )
        expected = {
            dimension: (definition_id, run.id)
            for dimension, definition_id in definition_ids.items()
        }
        actual = {
            row.dimension: (row.definition_id, row.decision_run_id) for row in existing
        }
        if existing:
            if actual != expected or any(row.scope_type != "INTERNAL_PILOT" for row in existing):
                raise ValueError(
                    "scope already has a different active definition set; retire it explicitly"
                )
            return ScoreActivationResult(
                scope_type="INTERNAL_PILOT",
                scope_key=scope_key,
                city_id=city_id,
                decision_run_id=run.id,
                definition_ids=definition_ids,
                created=False,
            )

        if apply:
            for dimension, definition_id in sorted(definition_ids.items()):
                self.session.add(
                    ScoreActivation(
                        scope_type="INTERNAL_PILOT",
                        scope_key=scope_key,
                        city_id=city_id,
                        dimension=dimension,
                        definition_id=definition_id,
                        decision_run_id=run.id,
                        decision_reason=decision_reason,
                    )
                )
            self.session.flush()
        return ScoreActivationResult(
            scope_type="INTERNAL_PILOT",
            scope_key=scope_key,
            city_id=city_id,
            decision_run_id=run.id,
            definition_ids=definition_ids,
            created=apply,
        )

    def _validated_run_definitions(self, run: ScoreRun) -> dict[str, uuid.UUID]:
        expected_dimensions = {dimension.value for dimension in ScoreDimension}
        rows = list(
            self.session.execute(
                select(
                    SignalDimensionEvaluation.dimension,
                    SignalDimensionEvaluation.definition_id,
                    SignalDimensionEvaluation.signal_id,
                ).where(SignalDimensionEvaluation.run_id == run.id)
            )
        )
        signals_by_dimension: dict[str, set[uuid.UUID]] = {
            dimension: set() for dimension in expected_dimensions
        }
        definitions_by_dimension: dict[str, set[uuid.UUID]] = {
            dimension: set() for dimension in expected_dimensions
        }
        for dimension, definition_id, signal_id in rows:
            if dimension not in expected_dimensions:
                raise ValueError("score run contains an unsupported dimension")
            signals_by_dimension[dimension].add(signal_id)
            definitions_by_dimension[dimension].add(definition_id)
        if any(
            len(signals) != run.population_size for signals in signals_by_dimension.values()
        ) or len({frozenset(signals) for signals in signals_by_dimension.values()}) != 1:
            raise ValueError("score run does not contain one complete shared signal population")
        if any(len(values) != 1 for values in definitions_by_dimension.values()):
            raise ValueError("score run does not contain exactly one definition per dimension")

        definition_ids = {
            dimension: next(iter(values))
            for dimension, values in definitions_by_dimension.items()
        }
        definitions = {
            row.id: row
            for row in self.session.scalars(
                select(ScoreDefinition).where(ScoreDefinition.id.in_(definition_ids.values()))
            )
        }
        for dimension, definition_id in definition_ids.items():
            definition = definitions.get(definition_id)
            if (
                definition is None
                or definition.dimension != dimension
                or definition.status != "CANDIDATE"
                or definition.feature_schema_revision != run.feature_schema_revision
            ):
                raise ValueError("score run definition is not an eligible candidate")
        return definition_ids

    def active_score_activations(
        self, *, scope_key: str, city_id: int
    ) -> list[tuple[ScoreActivation, ScoreDefinition, ScoreRun]]:
        return list(
            self.session.execute(
                select(ScoreActivation, ScoreDefinition, ScoreRun)
                .join(ScoreDefinition, ScoreDefinition.id == ScoreActivation.definition_id)
                .join(ScoreRun, ScoreRun.id == ScoreActivation.decision_run_id)
                .where(
                    ScoreActivation.scope_key == scope_key,
                    ScoreActivation.city_id == city_id,
                    ScoreActivation.retired_at.is_(None),
                )
                .order_by(ScoreActivation.dimension)
            )
        )

    def active_dimension_context(
        self, *, scope_key: str, city_id: int
    ) -> ActiveDimensionContext:
        rows = self.active_score_activations(scope_key=scope_key, city_id=city_id)
        expected_dimensions = {dimension.value for dimension in ScoreDimension}
        if len(rows) != len(expected_dimensions):
            raise ValueError("active dimension scope is incomplete")
        if {activation.dimension for activation, _, _ in rows} != expected_dimensions:
            raise ValueError("active dimension scope has an inconsistent dimension set")
        if any(
            activation.scope_type != "INTERNAL_PILOT"
            or definition.dimension != activation.dimension
            or run.id != activation.decision_run_id
            for activation, definition, run in rows
        ):
            raise ValueError("active dimension scope has inconsistent provenance")
        run_ids = {run.id for _, _, run in rows}
        hashes = {run.definition_set_hash for _, _, run in rows}
        as_of_dates = {run.as_of_date for _, _, run in rows}
        if len(run_ids) != 1 or len(hashes) != 1 or len(as_of_dates) != 1:
            raise ValueError("active dimensions do not share one immutable score run")
        return ActiveDimensionContext(
            scope_key=scope_key,
            city_id=city_id,
            run_id=next(iter(run_ids)),
            as_of_date=next(iter(as_of_dates)),
            definition_set_hash=next(iter(hashes)),
        )

    def active_signal_dimensions(
        self,
        *,
        scope_key: str,
        city_id: int,
        signal_ids: set[uuid.UUID] | None = None,
    ) -> dict[uuid.UUID, ActiveSignalDimensions]:
        active = active_dimensions_subquery(scope_key=scope_key, city_id=city_id)
        query = select(active)
        if signal_ids is not None:
            if not signal_ids:
                return {}
            query = query.where(active.c.signal_id.in_(signal_ids))
        rows = self.session.execute(query).mappings()
        return {
            row["signal_id"]: ActiveSignalDimensions(**row)
            for row in rows
        }
