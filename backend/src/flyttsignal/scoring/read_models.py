import uuid
from typing import Any

from flyttsignal.domains.signals.engines.metadata import ScoreDimension


class InconsistentScoreSet(ValueError):
    """Stored score rows cannot form one complete, reproducible read model."""


def dimension_score_payload(
    run: Any,
    signal_id: uuid.UUID,
    rows: list[tuple[Any, Any, Any]],
) -> dict[str, Any]:
    snapshot_ids = {snapshot.id for _, _, snapshot in rows}
    snapshot_hashes = {snapshot.payload_hash for _, _, snapshot in rows}
    expected_dimensions = {dimension.value for dimension in ScoreDimension}
    actual_dimensions = {result.dimension for result, _, _ in rows}
    inconsistent = any(
        definition.dimension != result.dimension
        or snapshot.signal_id != signal_id
        or snapshot.as_of_date != run.as_of_date
        or snapshot.feature_schema_revision != run.feature_schema_revision
        or definition.feature_schema_revision != run.feature_schema_revision
        for result, definition, snapshot in rows
    )
    if (
        len(snapshot_ids) != 1
        or len(snapshot_hashes) != 1
        or actual_dimensions != expected_dimensions
        or inconsistent
    ):
        raise InconsistentScoreSet("stored signal dimension score set is incomplete")
    return {
        "run_id": run.id,
        "signal_id": signal_id,
        "as_of_date": run.as_of_date,
        "feature_snapshot_id": next(iter(snapshot_ids)),
        "feature_snapshot_hash": next(iter(snapshot_hashes)),
        "dimensions": [
            {
                "dimension": result.dimension,
                "score": result.score,
                "components": result.components,
                "warnings": result.warnings,
                "definition": definition,
            }
            for result, definition, _ in rows
        ],
    }


def activation_payload(
    rows: list[tuple[Any, Any, Any]], *, scope_key: str, city_id: int
) -> dict[str, Any]:
    expected_dimensions = {dimension.value for dimension in ScoreDimension}
    decision_runs = {run.id for _, _, run in rows}
    actual_dimensions = {activation.dimension for activation, _, _ in rows}
    inconsistent = any(
        activation.scope_type != "INTERNAL_PILOT"
        or activation.scope_key != scope_key
        or activation.dimension != definition.dimension
        or activation.decision_run_id != run.id
        or activation.city_id != city_id
        or activation.city_id != run.city_id
        or definition.feature_schema_revision != run.feature_schema_revision
        for activation, definition, run in rows
    )
    if actual_dimensions != expected_dimensions or len(decision_runs) != 1 or inconsistent:
        raise InconsistentScoreSet("active score scope is incomplete or inconsistent")
    run = rows[0][2]
    return {
        "scope_type": "INTERNAL_PILOT",
        "scope_key": scope_key,
        "city_id": city_id,
        "decision_run_id": run.id,
        "as_of_date": run.as_of_date,
        "serving_mode": "INTERNAL_PILOT",
        "activations": [
            {
                "dimension": activation.dimension,
                "definition": definition,
                "activated_at": activation.activated_at,
                "decision_reason": activation.decision_reason,
            }
            for activation, definition, _ in rows
        ],
    }


def active_dimension_score_payload(
    activation_rows: list[tuple[Any, Any, Any]],
    result_rows: list[tuple[Any, Any, Any]],
    *,
    scope_key: str,
    city_id: int,
    signal_id: uuid.UUID,
) -> dict[str, Any]:
    activation_payload(activation_rows, scope_key=scope_key, city_id=city_id)
    activated_definitions = {
        activation.dimension: activation.definition_id
        for activation, _, _ in activation_rows
    }
    result_definitions = {
        result.dimension: definition.id for result, definition, _ in result_rows
    }
    if activated_definitions != result_definitions:
        raise InconsistentScoreSet("signal scores do not match the active definition set")
    return dimension_score_payload(
        activation_rows[0][2],
        signal_id,
        result_rows,
    )
