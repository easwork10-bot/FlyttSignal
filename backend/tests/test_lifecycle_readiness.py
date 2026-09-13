import uuid
from datetime import UTC, datetime, timedelta

from flyttsignal.db.models import RunStatus, RunTrigger, SourceRun
from flyttsignal.lifecycle.readiness import evaluate_lifecycle_readiness

NOW = datetime(2026, 8, 29, 12, tzinfo=UTC)


def run(
    age: int,
    *,
    trigger: RunTrigger = RunTrigger.SCHEDULED,
    status: RunStatus = RunStatus.SUCCESS,
    snapshot_status: str = "COMPLETE",
    rule: str = "source-v2",
    items_reported: int = 10,
    items_received: int = 10,
) -> SourceRun:
    started_at = NOW - timedelta(hours=age)
    return SourceRun(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        status=status,
        trigger_type=trigger.value,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        snapshot_status=snapshot_status,
        requests_attempted=1,
        requests_succeeded=1,
        requests_failed=0,
        pages_expected=1,
        pages_received=1,
        items_reported=items_reported,
        items_received=items_received,
        pagination_complete=True,
        hit_result_limit=False,
        inventory_scope_complete=True,
        completeness_rule_version=rule,
    )


def test_three_consecutive_complete_scheduled_runs_are_ready() -> None:
    result = evaluate_lifecycle_readiness([run(2), run(0), run(1)])

    assert result.ready is True
    assert result.qualifying_runs == 3
    assert result.reasons == ()


def test_manual_and_historical_runs_do_not_count() -> None:
    result = evaluate_lifecycle_readiness(
        [
            run(0, trigger=RunTrigger.MANUAL),
            run(1, trigger=RunTrigger.UNKNOWN),
        ]
    )

    assert result.ready is False
    assert result.qualifying_runs == 0
    assert result.reasons == ("no_scheduled_runs",)


def test_latest_incomplete_scheduled_run_breaks_the_streak() -> None:
    result = evaluate_lifecycle_readiness(
        [run(0, snapshot_status="INCOMPLETE"), run(1), run(2), run(3)]
    )

    assert result.ready is False
    assert result.qualifying_runs == 0
    assert "scheduled_snapshot_not_complete" in result.reasons


def test_rule_change_breaks_the_consecutive_streak() -> None:
    result = evaluate_lifecycle_readiness(
        [run(0, rule="source-v2"), run(1, rule="source-v1"), run(2, rule="source-v1")]
    )

    assert result.ready is False
    assert result.qualifying_runs == 1
    assert "completeness_rule_version_changed_or_missing" in result.reasons


def test_persisted_complete_label_cannot_override_bad_evidence() -> None:
    result = evaluate_lifecycle_readiness([run(0, items_received=9), run(1), run(2), run(3)])

    assert result.ready is False
    assert result.qualifying_runs == 0
    assert "scheduled_snapshot_evidence_not_complete" in result.reasons


def test_empty_complete_snapshot_cannot_establish_readiness() -> None:
    result = evaluate_lifecycle_readiness(
        [
            run(0, items_reported=0, items_received=0),
            run(1),
            run(2),
            run(3),
        ]
    )

    assert result.ready is False
    assert result.qualifying_runs == 0
    assert "scheduled_snapshot_empty" in result.reasons


def test_evaluation_is_read_only() -> None:
    runs = [run(0), run(1), run(2)]
    before = [dict(item.__dict__) for item in runs]

    evaluate_lifecycle_readiness(runs)

    assert [dict(item.__dict__) for item in runs] == before
