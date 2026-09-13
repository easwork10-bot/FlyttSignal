import json
import uuid
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from flyttsignal.db.models import (
    ScoreDefinition,
    ScoreRun,
    SignalDimensionEvaluation,
    SignalFeatureSnapshot,
)
from flyttsignal.db.repositories.feature_snapshots import PersistedFeatureSnapshot
from flyttsignal.domains.signals.engines.metadata import ScoreDimension
from flyttsignal.domains.signals.evaluation import (
    ScoreEvaluationService,
    create_evaluation_context,
)


@dataclass(frozen=True)
class PersistedScoreRun:
    run_id: uuid.UUID
    created: bool
    definitions_created: int
    evaluations_created: int
    definition_set_hash: str
    population_fingerprint: str


class ScoreRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def persist_dimension_run(
        self, *, city_id: int, snapshots: list[PersistedFeatureSnapshot]
    ) -> PersistedScoreRun:
        """Persist one complete candidate run or reuse its exact replay identity."""

        ordered = sorted(snapshots, key=lambda item: str(item.snapshot.signal_id))
        if not ordered:
            raise ValueError("score run requires at least one persisted snapshot")
        if len({item.snapshot.signal_id for item in ordered}) != len(ordered):
            raise ValueError("score run requires exactly one snapshot per signal")
        dates_and_schemas = {
            (item.snapshot.as_of_date, item.snapshot.schema_revision) for item in ordered
        }
        if len(dates_and_schemas) != 1:
            raise ValueError("score run requires one as_of date and feature schema")
        for item in ordered:
            if item.snapshot.fingerprint() != item.payload_hash:
                raise ValueError("persisted snapshot hash does not match its payload")

        as_of_date, feature_schema_revision = dates_and_schemas.pop()
        context = create_evaluation_context(as_of=as_of_date)
        service = ScoreEvaluationService()
        definitions = {
            dimension: service.definition(dimension, context)
            for dimension in ScoreDimension
        }
        definition_set_hash = _definition_set_hash(definitions)
        population_fingerprint = _population_fingerprint(ordered)
        identity = (
            ScoreRun.city_id == city_id,
            ScoreRun.as_of_date == as_of_date,
            ScoreRun.feature_schema_revision == feature_schema_revision,
            ScoreRun.definition_set_hash == definition_set_hash,
            ScoreRun.population_fingerprint == population_fingerprint,
        )
        existing_run = self.session.scalar(select(ScoreRun).where(*identity))
        if existing_run is not None:
            self._validate_existing_dimension_run(existing_run, ordered, definitions)
            return PersistedScoreRun(
                run_id=existing_run.id,
                created=False,
                definitions_created=0,
                evaluations_created=0,
                definition_set_hash=definition_set_hash,
                population_fingerprint=population_fingerprint,
            )

        definition_rows: dict[ScoreDimension, ScoreDefinition] = {}
        definitions_created = 0
        for dimension, (metadata, parameters) in definitions.items():
            row = self.session.get(ScoreDefinition, metadata.definition_id)
            expected = {
                "dimension": dimension.value,
                "definition_revision": metadata.definition_revision,
                "parameters": parameters,
                "parameter_hash": metadata.parameter_hash,
                "feature_schema_revision": metadata.feature_schema_revision,
                "engine_revision": metadata.engine_revision,
            }
            if row is None:
                row = ScoreDefinition(
                    id=metadata.definition_id,
                    status=metadata.status.value,
                    **expected,
                )
                self.session.add(row)
                definitions_created += 1
            elif any(getattr(row, key) != value for key, value in expected.items()):
                raise ValueError(f"score definition {metadata.definition_id} identity mismatch")
            definition_rows[dimension] = row

        run = ScoreRun(
            city_id=city_id,
            as_of_date=as_of_date,
            feature_schema_revision=feature_schema_revision,
            definition_set_hash=definition_set_hash,
            population_fingerprint=population_fingerprint,
            population_size=len(ordered),
            status="COMPLETE",
        )
        self.session.add(run)
        self.session.flush()
        for item in ordered:
            results = service.evaluate_all_dimensions(item.snapshot, context)
            for dimension, (result, metadata) in results.items():
                definition = definition_rows[dimension]
                if definition.id != metadata.definition_id:
                    raise ValueError("evaluation definition differs from registered definition")
                self.session.add(
                    SignalDimensionEvaluation(
                        run_id=run.id,
                        signal_id=item.snapshot.signal_id,
                        feature_snapshot_id=item.id,
                        definition_id=definition.id,
                        dimension=dimension.value,
                        score=result.score,
                        components=[
                            _component_payload(component) for component in result.components
                        ],
                        warnings=list(result.warnings),
                    )
                )
        self.session.flush()
        return PersistedScoreRun(
            run_id=run.id,
            created=True,
            definitions_created=definitions_created,
            evaluations_created=len(ordered) * len(ScoreDimension),
            definition_set_hash=definition_set_hash,
            population_fingerprint=population_fingerprint,
        )

    def _validate_existing_dimension_run(
        self,
        run: ScoreRun,
        snapshots: list[PersistedFeatureSnapshot],
        definitions: dict[ScoreDimension, tuple[Any, dict[str, Any]]],
    ) -> None:
        expected = {
            (item.snapshot.signal_id, item.id, dimension.value, metadata.definition_id)
            for item in snapshots
            for dimension, (metadata, _) in definitions.items()
        }
        actual = {
            (row.signal_id, row.feature_snapshot_id, row.dimension, row.definition_id)
            for row in self.session.scalars(
                select(SignalDimensionEvaluation).where(
                    SignalDimensionEvaluation.run_id == run.id
                )
            )
        }
        if actual != expected or run.population_size != len(snapshots):
            raise ValueError("existing score run is incomplete or inconsistent")

    def dimension_runs(self, *, city_id: int | None = None, limit: int = 20) -> list[ScoreRun]:
        query = select(ScoreRun).order_by(ScoreRun.created_at.desc()).limit(limit)
        if city_id is not None:
            query = query.where(ScoreRun.city_id == city_id)
        return list(self.session.scalars(query))

    def dimension_run(self, run_id: uuid.UUID) -> ScoreRun | None:
        return self.session.get(ScoreRun, run_id)

    def dimension_results(
        self, run_id: uuid.UUID, signal_id: uuid.UUID
    ) -> list[tuple[SignalDimensionEvaluation, ScoreDefinition, SignalFeatureSnapshot]]:
        return list(
            self.session.execute(
                select(SignalDimensionEvaluation, ScoreDefinition, SignalFeatureSnapshot)
                .join(
                    ScoreDefinition,
                    ScoreDefinition.id == SignalDimensionEvaluation.definition_id,
                )
                .join(
                    SignalFeatureSnapshot,
                    SignalFeatureSnapshot.id == SignalDimensionEvaluation.feature_snapshot_id,
                )
                .where(
                    SignalDimensionEvaluation.run_id == run_id,
                    SignalDimensionEvaluation.signal_id == signal_id,
                )
                .order_by(SignalDimensionEvaluation.dimension)
            )
        )


def _definition_set_hash(definitions: dict[ScoreDimension, tuple[Any, dict[str, Any]]]) -> str:
    payload = [
        {
            "definition_id": str(metadata.definition_id),
            "dimension": dimension.value,
            "parameter_hash": metadata.parameter_hash,
        }
        for dimension, (metadata, _) in sorted(definitions.items(), key=lambda item: item[0].value)
    ]
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode()).hexdigest()


def _population_fingerprint(snapshots: list[PersistedFeatureSnapshot]) -> str:
    value = "\n".join(
        f"{item.snapshot.signal_id}:{item.payload_hash}"
        for item in sorted(snapshots, key=lambda item: str(item.snapshot.signal_id))
    )
    return sha256(value.encode()).hexdigest()


def _component_payload(component: Any) -> dict[str, Any]:
    payload = {
        "component": component.component,
        "points": component.points,
        "reason": component.reason,
    }
    if component.metadata is not None:
        payload["metadata"] = component.metadata
    return payload
