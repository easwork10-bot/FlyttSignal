"""Read-only candidate replay over previously frozen feature snapshots."""

import json
from collections import Counter
from collections.abc import Sequence
from hashlib import sha256
from statistics import mean, median
from typing import Any

from flyttsignal.domains.signals.engines.metadata import ScoreDimension
from flyttsignal.domains.signals.evaluation import (
    ScoreEvaluationService,
    create_evaluation_context,
)
from flyttsignal.domains.signals.snapshots import FeatureSnapshot


def replay_snapshots(snapshots: Sequence[FeatureSnapshot]) -> dict[str, Any]:
    """Evaluate one frozen population without consulting mutable source state."""

    if not snapshots:
        raise ValueError("no persisted snapshots match the requested population")
    ordered = sorted(snapshots, key=lambda snapshot: str(snapshot.signal_id))
    if len({snapshot.signal_id for snapshot in ordered}) != len(ordered):
        raise ValueError("replay requires exactly one snapshot per signal")
    if len({(snapshot.as_of_date, snapshot.schema_revision) for snapshot in ordered}) != 1:
        raise ValueError("replay requires one as_of date and feature schema")

    service = ScoreEvaluationService()
    context = create_evaluation_context(as_of=ordered[0].as_of_date)
    items: list[dict[str, Any]] = []
    definitions: dict[str, Any] = {}
    for snapshot in ordered:
        dimensions: dict[str, Any] = {}
        for dimension, (result, metadata) in service.evaluate_all_dimensions(
            snapshot, context
        ).items():
            definitions[dimension.value] = {
                "definition_id": str(metadata.definition_id),
                "definition_revision": metadata.definition_revision,
                "engine_revision": metadata.engine_revision,
                "feature_schema_revision": metadata.feature_schema_revision,
                "parameter_hash": metadata.parameter_hash,
                "status": metadata.status.value,
            }
            dimensions[dimension.value] = {
                "score": result.score,
                "components": [
                    {
                        "component": component.component,
                        "points": component.points,
                        "reason": component.reason,
                    }
                    for component in result.components
                ],
                "warnings": list(result.warnings),
            }
        items.append(
            {
                "signal_id": str(snapshot.signal_id),
                "snapshot_hash": snapshot.fingerprint(),
                "dimensions": dimensions,
            }
        )

    population_input = "\n".join(
        f"{snapshot.signal_id}:{snapshot.fingerprint()}" for snapshot in ordered
    )
    report: dict[str, Any] = {
        "as_of_date": context.as_of.isoformat(),
        "feature_schema_revision": context.feature_schema_revision,
        "mode": "historical-shadow-replay",
        "population_size": len(ordered),
        "population_fingerprint": sha256(population_input.encode()).hexdigest(),
        "definitions": definitions,
        "summary": summarize_replay(items),
        "items": items,
    }
    canonical = json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    report["replay_fingerprint"] = sha256(canonical.encode()).hexdigest()
    return report


def summarize_replay(items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    for dimension in ScoreDimension:
        results = [item["dimensions"][dimension.value] for item in items]
        scores = [result["score"] for result in results]
        warnings = Counter(warning for result in results for warning in result["warnings"])
        histogram = Counter(scores)
        dimensions[dimension.value] = {
            "count": len(scores),
            "minimum": min(scores),
            "maximum": max(scores),
            "mean": round(mean(scores), 3),
            "median": median(scores),
            "score_histogram": {str(score): histogram[score] for score in sorted(histogram)},
            "signals_with_warnings": sum(bool(result["warnings"]) for result in results),
            "warning_counts": dict(sorted(warnings.items())),
        }
    combinations = Counter(
        "/".join(str(item["dimensions"][dimension.value]["score"]) for dimension in ScoreDimension)
        for item in items
    )
    return {
        "dimensions": dimensions,
        "score_combinations": dict(sorted(combinations.items())),
        "score_combination_order": [dimension.value for dimension in ScoreDimension],
    }
