from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from flyttsignal.db.models import RunStatus, RunTrigger, SourceRun
from flyttsignal.ingestion.contracts import SnapshotEvidence
from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus, assess_snapshot

REQUIRED_CONSECUTIVE_RUNS = 3


@dataclass(frozen=True)
class LifecycleReadiness:
    ready: bool
    required_runs: int
    qualifying_runs: int
    rule_version: str | None
    reasons: tuple[str, ...]
    considered_run_ids: tuple[UUID, ...]
    latest_scheduled_run_at: datetime | None


def _assessment(run: SourceRun):
    return assess_snapshot(
        SnapshotEvidence(
            requests_attempted=run.requests_attempted,
            requests_succeeded=run.requests_succeeded,
            requests_failed=run.requests_failed,
            pages_expected=run.pages_expected,
            pages_received=run.pages_received,
            items_reported=run.items_reported,
            items_received=run.items_received,
            pagination_complete=run.pagination_complete,
            hit_result_limit=run.hit_result_limit,
            inventory_scope_complete=run.inventory_scope_complete,
            rule_version=run.completeness_rule_version or "missing",
        )
    )


def evaluate_lifecycle_readiness(
    runs: list[SourceRun], *, required_runs: int = REQUIRED_CONSECUTIVE_RUNS
) -> LifecycleReadiness:
    """Evaluate recent runs without mutating any persisted state.

    Manual and historical UNKNOWN runs are deliberately ignored. The streak starts
    at the newest scheduled run and stops at the first failed integrity check or
    completeness-rule change.
    """

    scheduled = sorted(
        (run for run in runs if run.trigger_type == RunTrigger.SCHEDULED.value),
        key=lambda run: run.started_at,
        reverse=True,
    )
    if not scheduled:
        return LifecycleReadiness(
            ready=False,
            required_runs=required_runs,
            qualifying_runs=0,
            rule_version=None,
            reasons=("no_scheduled_runs",),
            considered_run_ids=(),
            latest_scheduled_run_at=None,
        )

    latest = scheduled[0]
    rule_version = latest.completeness_rule_version
    qualifying: list[SourceRun] = []
    blocker: str | None = None
    for run in scheduled:
        if not rule_version or run.completeness_rule_version != rule_version:
            blocker = "completeness_rule_version_changed_or_missing"
            break
        if run.status != RunStatus.SUCCESS or run.completed_at is None:
            blocker = "scheduled_execution_not_successful"
            break
        assessment = _assessment(run)
        if run.snapshot_status != SnapshotStatus.COMPLETE.value:
            blocker = "scheduled_snapshot_not_complete"
            break
        if assessment.status is not SnapshotStatus.COMPLETE:
            blocker = "scheduled_snapshot_evidence_not_complete"
            break
        if not run.items_received:
            blocker = "scheduled_snapshot_empty"
            break
        qualifying.append(run)
        if len(qualifying) == required_runs:
            break

    ready = len(qualifying) >= required_runs
    reasons: tuple[str, ...]
    if ready:
        reasons = ()
    elif blocker:
        reasons = (blocker, "insufficient_consecutive_complete_scheduled_runs")
    else:
        reasons = ("insufficient_consecutive_complete_scheduled_runs",)
    return LifecycleReadiness(
        ready=ready,
        required_runs=required_runs,
        qualifying_runs=len(qualifying),
        rule_version=rule_version,
        reasons=reasons,
        considered_run_ids=tuple(run.id for run in qualifying),
        latest_scheduled_run_at=latest.started_at,
    )
