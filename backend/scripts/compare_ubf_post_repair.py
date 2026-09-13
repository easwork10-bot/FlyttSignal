"""Compare current UBF semantics with one verified S6 capture without database writes."""

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from flyttsignal.db.repositories.feature_snapshots import FeatureSnapshotRepository
from flyttsignal.db.session import SessionLocal
from flyttsignal.scoring.observation import compare_captures, seal, validate_capture
from flyttsignal.scoring.replay import replay_snapshots

UBF_SOURCE_KEY = "uppsala_bostadsformedling_live_rentals"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _publisher_channels(snapshot: dict[str, Any]) -> set[str]:
    feature = snapshot["features"]["publisher_channel"]
    value = feature.get("value")
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def _subset(capture: dict[str, Any], signal_ids: set[str]) -> dict[str, Any]:
    return {
        "snapshots": [
            item for item in capture["snapshots"] if item["signal_id"] in signal_ids
        ],
        "replay": {
            **capture["replay"],
            "items": [
                item
                for item in capture["replay"]["items"]
                if item["signal_id"] in signal_ids
            ],
        },
    }


def _single_feature_value(snapshot: dict[str, Any], name: str) -> str:
    value = snapshot["features"][name].get("value")
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, str):
        raise ValueError(f"UBF comparison requires one {name} per signal")
    return value


def _ubf_by_source_item(capture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    replay_items = {
        item["signal_id"]: item for item in capture["replay"]["items"]
    }
    result: dict[str, dict[str, Any]] = {}
    for snapshot in capture["snapshots"]:
        if UBF_SOURCE_KEY not in _publisher_channels(snapshot):
            continue
        source_item_id = _single_feature_value(snapshot, "source_item_id")
        if source_item_id in result:
            raise ValueError("UBF source_item_id is not unique in the replay population")
        result[source_item_id] = {
            "signal_id": snapshot["signal_id"],
            "event_type": _single_feature_value(snapshot, "event_type"),
            "features": snapshot["features"],
            "dimensions": replay_items[snapshot["signal_id"]]["dimensions"],
        }
    return result


def _compare_ubf_source_items(
    baseline: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    before = _ubf_by_source_item(baseline)
    after = _ubf_by_source_item(current)
    shared = before.keys() & after.keys()
    dimensions = baseline["replay"]["definitions"]
    relinked = [
        key
        for key in sorted(shared)
        if before[key]["signal_id"] != after[key]["signal_id"]
    ]
    return {
        "baseline_size": len(before),
        "current_size": len(after),
        "shared_source_items": len(shared),
        "entered_source_items": sorted(after.keys() - before.keys()),
        "left_source_items": sorted(before.keys() - after.keys()),
        "relinked_signal_count": len(relinked),
        "relinked_items": [
            {
                "source_item_id": key,
                "before_signal_id": before[key]["signal_id"],
                "after_signal_id": after[key]["signal_id"],
                "event_type": f"{before[key]['event_type']}->{after[key]['event_type']}",
                "property_match": {
                    "before": before[key]["features"]["property_match"],
                    "after": after[key]["features"]["property_match"],
                },
                "unit_identifier_present": {
                    "before": before[key]["features"]["unit_identifier_present"],
                    "after": after[key]["features"]["unit_identifier_present"],
                },
                "scores": {
                    dimension: {
                        "before": before[key]["dimensions"][dimension]["score"],
                        "after": after[key]["dimensions"][dimension]["score"],
                    }
                    for dimension in dimensions
                },
            }
            for key in relinked
        ],
        "event_type_transitions": dict(
            sorted(
                Counter(
                    f"{before[key]['event_type']}->{after[key]['event_type']}"
                    for key in shared
                    if before[key]["event_type"] != after[key]["event_type"]
                ).items()
            )
        ),
        "changed_feature_counts": dict(
            sorted(
                Counter(
                    name
                    for key in shared
                    for name, value in after[key]["features"].items()
                    if value != before[key]["features"][name]
                ).items()
            )
        ),
        "score_delta_histograms": {
            dimension: dict(
                sorted(
                    Counter(
                        str(
                            after[key]["dimensions"][dimension]["score"]
                            - before[key]["dimensions"][dimension]["score"]
                        )
                        for key in shared
                    ).items()
                )
            )
            for dimension in dimensions
        },
    }


def _write_once(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--city-id", type=int, default=1)
    args = parser.parse_args()

    plan = _read(args.plan)
    baseline = _read(args.baseline)
    validate_capture(plan, baseline)
    captured_at = datetime.now(UTC)
    as_of_date = captured_at.astimezone(ZoneInfo("Europe/Stockholm")).date()
    if baseline["replay"]["as_of_date"] != as_of_date.isoformat():
        raise ValueError("post-repair comparison requires the baseline and current as_of date")

    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        snapshots = FeatureSnapshotRepository(session).build_current(
            city_id=args.city_id,
            as_of_date=as_of_date,
            captured_at=captured_at,
        )
        current_replay = replay_snapshots(snapshots)
        session.rollback()

    current = {
        "captured_at": captured_at.isoformat(),
        "snapshots": [snapshot.payload() for snapshot in snapshots],
        "replay": current_replay,
    }
    baseline_ubf_ids = {
        item["signal_id"]
        for item in baseline["snapshots"]
        if UBF_SOURCE_KEY in _publisher_channels(item)
    }
    current_ubf_ids = {
        item["signal_id"]
        for item in current["snapshots"]
        if UBF_SOURCE_KEY in _publisher_channels(item)
    }
    ubf_ids = baseline_ubf_ids | current_ubf_ids
    report = seal(
        {
            "mode": "read-only-post-repair-comparison",
            "generated_at": captured_at.isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "baseline": {
                "capture_hash": baseline["capture_hash"],
                "captured_at": baseline["captured_at"],
                "slot": baseline["slot"],
                "population_size": baseline["replay"]["population_size"],
                "population_fingerprint": baseline["replay"]["population_fingerprint"],
            },
            "current": {
                "captured_at": current["captured_at"],
                "population_size": current_replay["population_size"],
                "population_fingerprint": current_replay["population_fingerprint"],
                "replay_fingerprint": current_replay["replay_fingerprint"],
            },
            "all_signals": compare_captures(baseline, current),
            "ubf_signals": {
                "baseline_size": len(baseline_ubf_ids),
                "current_size": len(current_ubf_ids),
                **compare_captures(
                    _subset(baseline, ubf_ids),
                    _subset(current, ubf_ids),
                ),
            },
            "ubf_source_items": _compare_ubf_source_items(baseline, current),
            "definitions_unchanged": (
                baseline["replay"]["definitions"] == current_replay["definitions"]
            ),
            "candidate_activation_allowed": False,
        },
        "comparison_hash",
    )
    _write_once(args.output, report)
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"all_signals", "ubf_signals", "ubf_source_items"}
            }
            | {
                "all_signals": report["all_signals"],
                "ubf_signals": report["ubf_signals"],
                "ubf_source_items": report["ubf_source_items"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
