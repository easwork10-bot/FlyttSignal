"""Bounded shadow capture, input integrity, and safe unattended retry contracts."""

import importlib.util
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from flyttsignal.domains.signals.snapshots import FeatureSnapshot, present
from flyttsignal.scoring.observation import (
    capture_slot,
    compare_captures,
    create_plan,
    observation_status,
    seal,
    validate_capture,
)
from flyttsignal.scoring.replay import replay_snapshots
from flyttsignal.scoring.scenarios import scenario_catalog

START = datetime(2026, 9, 2, 18, tzinfo=UTC)


def snapshots(now=START):
    return [
        item.snapshot(as_of_date=now.astimezone(ZoneInfo("Europe/Stockholm")).date())
        for item in scenario_catalog()[:3]
    ]


@pytest.fixture
def plan():
    return create_plan(
        replay_snapshots(snapshots()), now=START, city_id=1, hours=72, interval_hours=3
    )


def capture(plan, now=START, inputs=None):
    inputs = snapshots(now) if inputs is None else inputs
    return seal(
        {
            "plan_hash": plan["plan_hash"],
            "slot": capture_slot(plan, now),
            "captured_at": now.isoformat(),
            "snapshots": [item.payload() for item in inputs],
            "replay": replay_snapshots(inputs),
            "source_health": [],
        },
        "capture_hash",
    )


def reseal(value, key):
    return seal({name: item for name, item in value.items() if name != key}, key)


def test_window_slots_are_half_open_and_not_backfilled(plan):
    assert plan["expected_captures"] == 24
    assert capture_slot(plan, START - timedelta(seconds=1)) is None
    assert capture_slot(plan, START) == 0
    assert capture_slot(plan, START + timedelta(hours=3)) == 1
    assert capture_slot(plan, START + timedelta(hours=72)) is None
    status = observation_status(plan, [capture(plan)], START + timedelta(hours=9))
    assert status["missed_closed_slots"] == [1, 2]
    assert status["observed_span_hours"] == 0
    ended = observation_status(plan, [capture(plan)], START + timedelta(hours=72))
    assert ended["state"] == "WINDOW_ENDED"
    assert ended["review_required"]
    assert ended["missed_closed_slots"] == list(range(1, 24))


@pytest.mark.parametrize("hours,interval", [(0, 3), (72, 0), (8, 3), (169, 1), (2, 3)])
def test_plan_rejects_invalid_windows(hours, interval):
    with pytest.raises(ValueError, match="window"):
        create_plan(
            replay_snapshots(snapshots()),
            now=START,
            city_id=1,
            hours=hours,
            interval_hours=interval,
        )


def test_plan_rejects_naive_time_and_unsealed_reference(plan):
    with pytest.raises(ValueError, match="timezone"):
        capture_slot(plan, START.replace(tzinfo=None))
    with pytest.raises(ValueError, match="integrity"):
        create_plan({}, now=START, city_id=1, hours=72, interval_hours=3)


def test_capture_roundtrip_and_hash_tampering(plan):
    value = json.loads(json.dumps(capture(plan)))
    validate_capture(plan, value)
    value["slot"] = 1
    with pytest.raises(ValueError, match="integrity"):
        validate_capture(plan, value)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("definition", "definition drift"),
        ("plan", "different observation"),
        ("slot", "timestamp"),
        ("input", "population"),
        ("duplicate_input", "population"),
        ("duplicate_output", "population"),
        ("size", "population"),
        ("date", "date/schema"),
        ("schema", "schema drift"),
    ],
)
def test_semantic_integrity_is_checked_even_with_recomputed_hashes(plan, change, reason):
    value = deepcopy(capture(plan))
    report = value["replay"]
    if change == "definition":
        next(iter(report["definitions"].values()))["parameter_hash"] = "different"
    elif change == "plan":
        value["plan_hash"] = "different"
    elif change == "slot":
        value["slot"] = 1
    elif change == "input":
        value["snapshots"].pop()
    elif change == "duplicate_input":
        value["snapshots"].append(value["snapshots"][0])
    elif change == "duplicate_output":
        report["items"].append(report["items"][0])
    elif change == "size":
        report["population_size"] += 1
    elif change == "date":
        report["as_of_date"] = "2026-09-01"
    elif change == "schema":
        report["feature_schema_revision"] = "different"
    value["replay"] = reseal(report, "replay_fingerprint")
    with pytest.raises(ValueError, match=reason):
        validate_capture(plan, reseal(value, "capture_hash"))


def test_status_rejects_duplicate_slots(plan):
    value = capture(plan)
    with pytest.raises(ValueError, match="duplicate capture"):
        observation_status(plan, [value, value], START)


def test_comparison_separates_membership_and_feature_changes(plan):
    old = snapshots()
    modified = FeatureSnapshot(
        old[1].signal_id,
        old[1].as_of_date,
        {**old[1].features, "evidence_count": present(99)},
        old[1].schema_revision,
    )
    before = capture(plan, inputs=old[:2])
    after = capture(plan, START + timedelta(hours=3), [modified, old[2]])
    comparison = compare_captures(before, after)
    assert comparison["entered_population"] == [str(old[2].signal_id)]
    assert comparison["left_population"] == [str(old[0].signal_id)]
    assert comparison["changed_feature_counts"] == {"evidence_count": 1}
    assert comparison["shared_signals"] == 1
    for histogram in comparison["score_delta_histograms"].values():
        assert sum(histogram.values()) == 1


def test_capture_date_uses_stockholm_and_accepts_day_boundary(plan):
    now = START + timedelta(hours=4)  # 00:00 Stockholm, next calendar day.
    value = capture(plan, now)
    assert value["replay"]["as_of_date"] == "2026-09-03"
    validate_capture(plan, value)


@pytest.fixture
def cli():
    path = Path(__file__).parents[1] / "scripts" / "observe_signal_engines.py"
    spec = importlib.util.spec_from_file_location("observe_signal_engines", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_artifact_writer_never_overwrites(cli, tmp_path):
    path = tmp_path / "capture-000.json"
    cli.write_once(path, {"original": True})
    with pytest.raises(FileExistsError):
        cli.write_once(path, {"original": False})
    assert cli.read_json(path) == {"original": True}


@pytest.mark.parametrize("action,elapsed", [("status", 0), ("capture", 0), ("capture", 72)])
def test_status_repeat_and_ended_window_never_open_database(
    cli, plan, tmp_path, monkeypatch, capsys, action, elapsed
):
    cli.write_once(tmp_path / "observation.json", plan)
    cli.write_once(tmp_path / "capture-000.json", capture(plan))

    class Clock:
        @staticmethod
        def now(tz):
            return START + timedelta(hours=elapsed)

    def forbidden():
        raise AssertionError("database must not be accessed")

    monkeypatch.setattr(cli, "datetime", Clock)
    monkeypatch.setattr(cli, "SessionLocal", forbidden)
    monkeypatch.setattr(sys, "argv", ["observe", action, "--directory", str(tmp_path)])
    cli.main()
    status = json.loads(capsys.readouterr().out)
    assert status["captured_slots"] == [0]
    assert len(list(tmp_path.glob("capture-*.json"))) == 1


def test_capture_loader_rejects_misnamed_artifact(cli, plan, tmp_path):
    cli.write_once(tmp_path / "capture-001.json", capture(plan))
    with pytest.raises(ValueError, match="filename"):
        cli.load_captures(tmp_path)
