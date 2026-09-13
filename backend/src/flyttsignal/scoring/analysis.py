"""Deterministic validation analysis over verified live-observation captures."""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from flyttsignal.scoring.observation import (
    compare_captures,
    observation_status,
    seal,
)


def analyze_observation(
    plan: dict[str, Any], captures: list[dict[str, Any]], *, now: datetime
) -> dict[str, Any]:
    """Analyze only captured facts and leave candidate selection to human review."""

    if not captures:
        raise ValueError("analysis requires at least one observation capture")
    status = observation_status(plan, captures, now)
    ordered = sorted(captures, key=lambda item: item["slot"])
    transitions = [
        compare_captures(previous, current)
        for previous, current in zip(ordered, ordered[1:], strict=False)
    ]
    population = _population_analysis(ordered, transitions)
    source_health = _source_health_analysis(ordered)
    scores = _score_analysis(ordered)
    warnings = _warning_analysis(ordered)
    outcomes = _outcome_analysis(ordered)

    window_complete = status["state"] == "WINDOW_ENDED"
    complete_coverage = (
        window_complete
        and not status["missed_closed_slots"]
        and len(ordered) == plan["expected_captures"]
    )
    if not window_complete:
        conclusion = "PRELIMINARY"
    elif not complete_coverage:
        conclusion = "INCOMPLETE_FOR_REVIEW"
    else:
        conclusion = "READY_FOR_HUMAN_REVIEW"

    report = {
        "analysis_as_of": now.isoformat(),
        "plan_hash": plan["plan_hash"],
        "conclusion": conclusion,
        "candidate_activation_allowed": False,
        "coverage": {
            "state": status["state"],
            "expected_captures": plan["expected_captures"],
            "captured_count": len(ordered),
            "captured_slots": status["captured_slots"],
            "missed_closed_slots": status["missed_closed_slots"],
            "observed_span_hours": status["observed_span_hours"],
        },
        "gates": [
            _gate("artifact_integrity", "PASS", "every loaded plan/capture hash was verified"),
            _gate(
                "window_complete",
                "PASS" if window_complete else "PENDING",
                status["ends_at"],
            ),
            _gate(
                "capture_coverage",
                "PASS" if complete_coverage else ("FAIL" if window_complete else "PENDING"),
                f"{len(ordered)}/{plan['expected_captures']} captures",
            ),
            _gate(
                "source_freshness",
                "NEEDS_REVIEW" if source_health["captures_with_issues"] else "PASS",
                (
                    f"{source_health['captures_with_issues']} captures contain a stale "
                    "or unhealthy source"
                ),
            ),
            _gate(
                "move_outcome_validation",
                "NOT_MEASURABLE" if outcomes["confirmed_move_signals"] == 0 else "NEEDS_REVIEW",
                f"{outcomes['confirmed_move_signals']} signals have a confirmed move outcome",
            ),
        ],
        "population": population,
        "source_health": source_health,
        "scores": scores,
        "warnings": warnings,
        "outcomes": outcomes,
        "definitions": plan["definitions"],
    }
    return seal(report, "analysis_hash")


def _gate(name: str, state: str, evidence: str) -> dict[str, str]:
    return {"gate": name, "state": state, "evidence": evidence}


def _population_analysis(
    captures: list[dict[str, Any]], transitions: list[dict[str, Any]]
) -> dict[str, Any]:
    populations = [set(item["signal_id"] for item in capture["snapshots"]) for capture in captures]
    feature_changes: Counter[str] = Counter()
    for change in transitions:
        feature_changes.update(change["changed_feature_counts"])
    entered = {signal_id for change in transitions for signal_id in change["entered_population"]}
    left = {signal_id for change in transitions for signal_id in change["left_population"]}
    return {
        "first_size": len(populations[0]),
        "latest_size": len(populations[-1]),
        "minimum_size": min(map(len, populations)),
        "maximum_size": max(map(len, populations)),
        "union_size": len(set.union(*populations)),
        "persistent_size": len(set.intersection(*populations)),
        "entered_signal_ids": sorted(entered),
        "left_signal_ids": sorted(left),
        "feature_change_counts": dict(sorted(feature_changes.items())),
    }


def _source_health_analysis(captures: list[dict[str, Any]]) -> dict[str, Any]:
    observations: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"observations": 0, "stale_count": 0, "unhealthy_count": 0}
    )
    captures_with_issues = 0
    for capture in captures:
        issue = False
        for source in capture["source_health"]:
            item = observations[source["key"]]
            item["observations"] += 1
            item["stale_count"] += int(source["stale"])
            item["unhealthy_count"] += int(source["status"] != "HEALTHY")
            item["latest_status"] = source["status"]
            item["latest_success_at"] = source["last_success_at"]
            issue = issue or source["stale"] or source["status"] != "HEALTHY"
        captures_with_issues += int(issue)
    return {
        "captures_with_issues": captures_with_issues,
        "sources": {name: item for name, item in sorted(observations.items())},
    }


def _score_analysis(captures: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = captures[0]["replay"]["definitions"]
    aggregate: dict[str, dict[str, Any]] = {}
    for dimension in dimensions:
        delta_counts: Counter[int] = Counter()
        changed_signals: set[str] = set()
        comparisons = 0
        for previous, current in zip(captures, captures[1:], strict=False):
            old = _dimension_scores(previous, dimension)
            new = _dimension_scores(current, dimension)
            for signal_id in old.keys() & new.keys():
                delta = new[signal_id] - old[signal_id]
                delta_counts[delta] += 1
                comparisons += 1
                if delta:
                    changed_signals.add(signal_id)
        aggregate[dimension] = {
            "first_summary": captures[0]["replay"]["summary"]["dimensions"][dimension],
            "latest_summary": captures[-1]["replay"]["summary"]["dimensions"][dimension],
            "shared_transition_comparisons": comparisons,
            "changed_signal_count": len(changed_signals),
            "increases": sum(count for delta, count in delta_counts.items() if delta > 0),
            "decreases": sum(count for delta, count in delta_counts.items() if delta < 0),
            "unchanged": delta_counts[0],
            "delta_histogram": {str(key): delta_counts[key] for key in sorted(delta_counts)},
        }
    return aggregate


def _dimension_scores(capture: dict[str, Any], dimension: str) -> dict[str, int]:
    return {
        item["signal_id"]: item["dimensions"][dimension]["score"]
        for item in capture["replay"]["items"]
    }


def _warning_analysis(captures: list[dict[str, Any]]) -> dict[str, Any]:
    first = _warnings(captures[0])
    latest = _warnings(captures[-1])
    changed: set[str] = set()
    comparisons = 0
    for previous, current in zip(captures, captures[1:], strict=False):
        before = _warning_sets(previous)
        after = _warning_sets(current)
        for key in before.keys() & after.keys():
            comparisons += 1
            if before[key] != after[key]:
                changed.add(":".join(key))
    return {
        "first_counts": dict(sorted(first.items())),
        "latest_counts": dict(sorted(latest.items())),
        "shared_transition_comparisons": comparisons,
        "changed_signal_dimension_count": len(changed),
    }


def _warnings(capture: dict[str, Any]) -> Counter[str]:
    return Counter(
        warning
        for item in capture["replay"]["items"]
        for result in item["dimensions"].values()
        for warning in result["warnings"]
    )


def _warning_sets(capture: dict[str, Any]) -> dict[tuple[str, str], frozenset[str]]:
    return {
        (item["signal_id"], dimension): frozenset(result["warnings"])
        for item in capture["replay"]["items"]
        for dimension, result in item["dimensions"].items()
    }


def _outcome_analysis(captures: list[dict[str, Any]]) -> dict[str, Any]:
    observed: dict[str, set[str]] = defaultdict(set)
    for capture in captures:
        for snapshot in capture["snapshots"]:
            item = snapshot["features"]["outcome_types"]
            if item["state"] == "PRESENT":
                observed[snapshot["signal_id"]].update(item.get("value", []))
    counts = Counter(outcome for values in observed.values() for outcome in values)
    return {
        "signals_with_any_outcome": sum(bool(values) for values in observed.values()),
        "confirmed_move_signals": sum("CONFIRMED_MOVE" in values for values in observed.values()),
        "outcome_type_signal_counts": dict(sorted(counts.items())),
        # A bounded observational sample can support review, not prove calibration by itself.
        "calibration_claim_allowed": False,
    }
