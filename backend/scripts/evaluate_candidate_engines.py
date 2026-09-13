"""Run deterministic candidate engines against the frozen S3 scenario catalog."""

import argparse
import json
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

from flyttsignal.domains.signals.engines.metadata import ScoreDimension
from flyttsignal.domains.signals.evaluation import (
    ScoreEvaluationService,
    create_evaluation_context,
)
from flyttsignal.scoring.scenarios import scenario_catalog, scenario_catalog_fingerprint


def evaluate_scenarios(as_of: date) -> dict[str, Any]:
    service = ScoreEvaluationService()
    context = create_evaluation_context(as_of=as_of)
    catalog = scenario_catalog()
    scenarios: dict[str, Any] = {}

    for scenario in catalog:
        snapshot = scenario.snapshot(as_of_date=as_of)
        dimensions: dict[str, Any] = {}
        for dimension, (result, metadata) in service.evaluate_all_dimensions(
            snapshot, context
        ).items():
            dimensions[dimension.value] = {
                "components": [
                    {
                        "component": component.component,
                        "points": component.points,
                        "reason": component.reason,
                    }
                    for component in result.components
                ],
                "definition": {
                    "definition_id": str(metadata.definition_id),
                    "definition_revision": metadata.definition_revision,
                    "engine_revision": metadata.engine_revision,
                    "feature_schema_revision": metadata.feature_schema_revision,
                    "parameter_hash": metadata.parameter_hash,
                },
                "score": result.score,
                "warnings": list(result.warnings),
            }
        scenarios[scenario.key] = {
            "description": scenario.description,
            "dimensions": dimensions,
            "family": scenario.family.value,
            "invariants": sorted(scenario.invariants),
            "snapshot_hash": snapshot.fingerprint(),
        }

    failures = validate_invariants(scenarios)
    result: dict[str, Any] = {
        "as_of": as_of.isoformat(),
        "catalog_fingerprint": scenario_catalog_fingerprint(as_of_date=as_of),
        "invariant_failures": failures,
        "scenario_count": len(catalog),
        "scenarios": scenarios,
    }
    canonical = json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    result["evaluation_fingerprint"] = sha256(canonical.encode()).hexdigest()
    return result


def validate_invariants(scenarios: dict[str, Any]) -> list[str]:
    """Validate the cross-scenario rules that protect meaning and monotonicity."""

    failures: list[str] = []
    baseline_scores = _scores(scenarios["classification-apartment"])

    for key, scenario in scenarios.items():
        invariants = set(scenario["invariants"])
        scores = _scores(scenario)
        protected = {"commercial_only", "confidence_not_strength", "strength_unchanged"}
        if invariants & protected:
            strength = ScoreDimension.SIGNAL_STRENGTH.value
            if scores[strength] != baseline_scores[strength]:
                failures.append(f"{key}: non-strength input changed Signal Strength")
        if "warning_required" in invariants and not any(
            dimension["warnings"] for dimension in scenario["dimensions"].values()
        ):
            failures.append(f"{key}: expected an explicit warning")
        if "no_safe_removal" in invariants and any(
            component["component"] == "removal_candidate" and component["points"] > 0
            for component in scenario["dimensions"][ScoreDimension.TIMING.value]["components"]
        ):
            failures.append(f"{key}: unsafe removal urgency bonus")
        if "no_match_is_not_invalid_data" in invariants:
            result = scenario["dimensions"][ScoreDimension.DATA_CONFIDENCE.value]
            reuse = [
                item for item in result["components"] if item["component"] == "property_not_reused"
            ]
            if len(reuse) != 1 or reuse[0]["points"] != 0:
                failures.append(f"{key}: no reused property must be neutral, not invalid data")

    duplicate = _scores(scenarios["duplicate-observations-one-provenance"])
    corroborated = _scores(scenarios["independent-corroboration"])
    strength = ScoreDimension.SIGNAL_STRENGTH.value
    if duplicate[strength] != baseline_scores[strength]:
        failures.append("duplicate observations were treated as independent")
    if corroborated[strength] <= duplicate[strength]:
        failures.append("independent corroboration did not strengthen evidence")

    missing_scores = _scores(scenarios["available-date-missing"])
    for dimension in (ScoreDimension.SIGNAL_STRENGTH, ScoreDimension.TIMING):
        if missing_scores[dimension.value] > baseline_scores[dimension.value]:
            failures.append(f"missing available date improved {dimension.value}")

    confidence = ScoreDimension.DATA_CONFIDENCE.value
    no_reuse = _scores(scenarios["no-property-match"])[confidence]
    uncertain = _scores(scenarios["uncertain-property-match"])[confidence]
    if not uncertain < no_reuse < baseline_scores[confidence]:
        failures.append("property reuse must distinguish uncertain, not reused, and strong")
    for key in ("property-match-missing", "property-match-conflicting"):
        if _scores(scenarios[key])[confidence] > uncertain:
            failures.append(f"{key}: unknown/conflicting reuse improved identity confidence")
    if _scores(scenarios["new-property-without-unit-identifier"])[confidence] >= no_reuse:
        failures.append("missing unit identity must remain a separate confidence limitation")

    quality_cases = (
        "coordinates-missing",
        "unit-identifier-missing",
        "source-item-identity-missing",
    )
    for key in quality_cases:
        if _scores(scenarios[key])[confidence] >= baseline_scores[confidence]:
            failures.append(f"{key}: missing identity or spatial data did not reduce confidence")

    timing = ScoreDimension.TIMING.value
    if _scores(scenarios["available-minus-1-days"])[timing] >= _scores(
        scenarios["available-plus-0-days"]
    )[timing]:
        failures.append("a past availability date was scored as immediate/future timing")

    age_scores = [
        _scores(scenarios[f"signal-age-{age}-days"])[timing]
        for age in (0, 1, 30, 31, 90, 91, 120, 121, 365)
    ]
    if age_scores != sorted(age_scores, reverse=True):
        failures.append("older signals can improve Timing")

    return sorted(failures)


def _scores(scenario: dict[str, Any]) -> dict[str, int]:
    return {
        dimension: details["score"]
        for dimension, details in scenario["dimensions"].items()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_scenarios(args.as_of)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if result["invariant_failures"]:
        print(f"candidate evaluation failed {len(result['invariant_failures'])} invariants")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
