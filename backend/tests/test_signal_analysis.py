"""S7 analysis is reproducible, honest about coverage, and never self-activating."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from flyttsignal.domains.signals.snapshots import FeatureSnapshot, present
from flyttsignal.scoring.analysis import analyze_observation
from flyttsignal.scoring.observation import capture_slot, create_plan, seal
from flyttsignal.scoring.replay import replay_snapshots
from flyttsignal.scoring.scenarios import scenario_catalog

START = datetime(2026, 9, 5, 18, tzinfo=UTC)


def snapshot(now=START, *, listing_status=None, outcome_types=None):
    original = scenario_catalog()[0].snapshot(
        as_of_date=now.astimezone(ZoneInfo("Europe/Stockholm")).date()
    )
    features = dict(original.features)
    if listing_status is not None:
        features["listing_status"] = present(listing_status)
    if outcome_types is not None:
        features["outcome_types"] = present(outcome_types)
    return FeatureSnapshot(
        original.signal_id, original.as_of_date, features, original.schema_revision
    )


def make_plan(hours=6):
    return create_plan(
        replay_snapshots([snapshot()]),
        now=START,
        city_id=1,
        hours=hours,
        interval_hours=3,
    )


def capture(plan, now, item=None, *, stale=False, status="HEALTHY"):
    item = item or snapshot(now)
    return seal(
        {
            "plan_hash": plan["plan_hash"],
            "slot": capture_slot(plan, now),
            "captured_at": now.isoformat(),
            "snapshots": [item.payload()],
            "replay": replay_snapshots([item]),
            "source_health": [
                {
                    "key": "source",
                    "status": status,
                    "stale": stale,
                    "last_success_at": now.isoformat(),
                }
            ],
        },
        "capture_hash",
    )


def test_running_window_is_preliminary_and_never_allows_activation():
    plan = make_plan()
    report = analyze_observation(plan, [capture(plan, START)], now=START)
    assert report["conclusion"] == "PRELIMINARY"
    assert report["candidate_activation_allowed"] is False
    assert report["coverage"]["captured_count"] == 1
    assert {gate["gate"]: gate["state"] for gate in report["gates"]}["window_complete"] == "PENDING"


def test_complete_window_becomes_ready_only_for_human_review():
    plan = make_plan()
    captures = [capture(plan, START), capture(plan, START + timedelta(hours=3))]
    report = analyze_observation(plan, captures, now=START + timedelta(hours=6))
    assert report["conclusion"] == "READY_FOR_HUMAN_REVIEW"
    assert report["candidate_activation_allowed"] is False
    assert report["coverage"]["captured_slots"] == [0, 1]


def test_ended_window_with_gap_is_explicitly_incomplete():
    plan = make_plan(hours=9)
    captures = [capture(plan, START), capture(plan, START + timedelta(hours=6))]
    report = analyze_observation(plan, captures, now=START + timedelta(hours=9))
    assert report["conclusion"] == "INCOMPLETE_FOR_REVIEW"
    assert report["coverage"]["missed_closed_slots"] == [1]
    assert {gate["gate"]: gate["state"] for gate in report["gates"]}["capture_coverage"] == "FAIL"


def test_analysis_tracks_source_feature_score_warning_and_outcome_changes():
    plan = make_plan()
    first = capture(plan, START, stale=True)
    changed = snapshot(
        START + timedelta(hours=3),
        listing_status="REMOVED",
        outcome_types=["CONFIRMED_MOVE"],
    )
    second = capture(plan, START + timedelta(hours=3), changed, status="FAILED")
    report = analyze_observation(plan, [first, second], now=START + timedelta(hours=6))
    assert report["population"]["feature_change_counts"] == {
        "listing_status": 1,
        "outcome_types": 1,
    }
    assert report["source_health"]["captures_with_issues"] == 2
    assert report["source_health"]["sources"]["source"]["stale_count"] == 1
    assert report["source_health"]["sources"]["source"]["unhealthy_count"] == 1
    assert report["outcomes"]["confirmed_move_signals"] == 1
    assert report["outcomes"]["calibration_claim_allowed"] is False
    assert any(item["changed_signal_count"] == 1 for item in report["scores"].values())


def test_no_confirmed_moves_prohibits_calibration_claim():
    plan = make_plan()
    report = analyze_observation(plan, [capture(plan, START)], now=START)
    assert report["outcomes"]["confirmed_move_signals"] == 0
    assert report["outcomes"]["calibration_claim_allowed"] is False
    assert {gate["gate"]: gate["state"] for gate in report["gates"]}[
        "move_outcome_validation"
    ] == "NOT_MEASURABLE"


def test_analysis_revalidates_capture_integrity():
    plan = make_plan()
    damaged = deepcopy(capture(plan, START))
    damaged["snapshots"][0]["signal_id"] = "damaged"
    with pytest.raises(ValueError, match="integrity"):
        analyze_observation(plan, [damaged], now=START)


def test_analysis_requires_observed_data():
    with pytest.raises(ValueError, match="at least one"):
        analyze_observation(make_plan(), [], now=START)
