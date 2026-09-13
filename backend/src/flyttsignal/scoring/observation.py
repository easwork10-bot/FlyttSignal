"""Bounded observation windows and comparisons of immutable capture artifacts."""

import json
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo


def fingerprint(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode()).hexdigest()


def seal(value: dict[str, Any], key: str) -> dict[str, Any]:
    return {**value, key: fingerprint(value)}


def verify(value: dict[str, Any], key: str) -> None:
    if value.get(key) != fingerprint({name: item for name, item in value.items() if name != key}):
        raise ValueError(f"artifact failed {key} integrity check")


def create_plan(
    reference: dict[str, Any], *, now: datetime, city_id: int, hours: int, interval_hours: int
) -> dict[str, Any]:
    verify(reference, "replay_fingerprint")
    if now.tzinfo is None:
        raise ValueError("observation requires timezone-aware time")
    if not 1 <= interval_hours <= hours <= 168 or hours % interval_hours:
        raise ValueError("window must be divisible by its interval and at most seven days")
    if city_id <= 0:
        raise ValueError("city_id must be positive")
    return seal(
        {
            "started_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=hours)).isoformat(),
            "interval_hours": interval_hours,
            "expected_captures": hours // interval_hours,
            "city_id": city_id,
            "definitions": reference["definitions"],
            "feature_schema_revision": reference["feature_schema_revision"],
            "reference_replay_fingerprint": reference["replay_fingerprint"],
        },
        "plan_hash",
    )


def capture_slot(plan: dict[str, Any], now: datetime) -> int | None:
    verify(plan, "plan_hash")
    if now.tzinfo is None:
        raise ValueError("observation requires timezone-aware time")
    start = datetime.fromisoformat(plan["started_at"])
    end = datetime.fromisoformat(plan["ends_at"])
    if now < start or now >= end:
        return None
    return int((now - start).total_seconds() // (plan["interval_hours"] * 3600))


def validate_capture(plan: dict[str, Any], capture: dict[str, Any]) -> None:
    verify(capture, "capture_hash")
    if capture["plan_hash"] != plan["plan_hash"]:
        raise ValueError("capture belongs to a different observation plan")
    captured_at = datetime.fromisoformat(capture["captured_at"])
    slot = capture_slot(plan, captured_at)
    if slot is None or slot != capture["slot"]:
        raise ValueError("capture timestamp does not belong to its slot")
    report = capture["replay"]
    verify(report, "replay_fingerprint")
    if report["definitions"] != plan["definitions"]:
        raise ValueError("candidate definition drift: start a separately approved observation")
    if report["feature_schema_revision"] != plan["feature_schema_revision"]:
        raise ValueError("feature schema drift")
    as_of_date = captured_at.astimezone(ZoneInfo("Europe/Stockholm")).date().isoformat()
    if report["as_of_date"] != as_of_date or any(
        item["as_of_date"] != as_of_date
        or item["schema_revision"] != plan["feature_schema_revision"]
        for item in capture["snapshots"]
    ):
        raise ValueError("capture date/schema differs from its inputs")
    inputs = {item["signal_id"]: fingerprint(item) for item in capture["snapshots"]}
    outputs = {item["signal_id"]: item["snapshot_hash"] for item in report["items"]}
    if (
        not inputs
        or inputs != outputs
        or len(inputs) != len(capture["snapshots"])
        or len(outputs) != len(report["items"])
        or report["population_size"] != len(inputs)
    ):
        raise ValueError("capture inputs differ from replay population")


def observation_status(
    plan: dict[str, Any], captures: list[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    verify(plan, "plan_hash")
    for capture in captures:
        validate_capture(plan, capture)
    slots = {capture["slot"] for capture in captures}
    if len(slots) != len(captures):
        raise ValueError("duplicate capture slot")
    ordered = sorted(captures, key=lambda item: item["slot"])
    ended = now >= datetime.fromisoformat(plan["ends_at"])
    current_slot = capture_slot(plan, now)
    closed_slots = plan["expected_captures"] if ended else (current_slot or 0)
    return {
        "state": "WINDOW_ENDED" if ended else "OBSERVING",
        "started_at": plan["started_at"],
        "ends_at": plan["ends_at"],
        "expected_captures": plan["expected_captures"],
        "captured_slots": sorted(slots),
        "missed_closed_slots": sorted(set(range(closed_slots)) - slots),
        "observed_span_hours": (
            (
                datetime.fromisoformat(ordered[-1]["captured_at"])
                - datetime.fromisoformat(ordered[0]["captured_at"])
            ).total_seconds()
            / 3600
            if ordered
            else 0
        ),
        "latest_summary": ordered[-1]["replay"]["summary"] if ordered else None,
        "latest_source_health": ordered[-1]["source_health"] if ordered else [],
        "change_from_previous": compare_captures(ordered[-2], ordered[-1])
        if len(ordered) > 1
        else None,
        "review_required": ended,
    }


def compare_captures(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old = {item["signal_id"]: item for item in previous["snapshots"]}
    new = {item["signal_id"]: item for item in current["snapshots"]}
    shared = old.keys() & new.keys()
    feature_changes = Counter(
        name
        for signal_id in shared
        for name, value in new[signal_id]["features"].items()
        if value != old[signal_id]["features"][name]
    )
    before = {item["signal_id"]: item["dimensions"] for item in previous["replay"]["items"]}
    after = {item["signal_id"]: item["dimensions"] for item in current["replay"]["items"]}
    return {
        "entered_population": sorted(new.keys() - old.keys()),
        "left_population": sorted(old.keys() - new.keys()),
        "shared_signals": len(shared),
        "changed_feature_counts": dict(sorted(feature_changes.items())),
        "score_delta_histograms": {
            dimension: dict(
                sorted(
                    Counter(
                        str(
                            after[signal_id][dimension]["score"]
                            - before[signal_id][dimension]["score"]
                        )
                        for signal_id in shared
                    ).items()
                )
            )
            for dimension in current["replay"]["definitions"]
        },
    }
