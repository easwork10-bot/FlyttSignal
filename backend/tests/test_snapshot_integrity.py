from flyttsignal.db.models import SourceRun
from flyttsignal.ingestion.contracts import SnapshotEvidence, SourceAdapter
from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus, assess_snapshot


def evidence(**overrides) -> SnapshotEvidence:
    values = {
        "requests_attempted": 2,
        "requests_succeeded": 2,
        "requests_failed": 0,
        "pages_expected": 2,
        "pages_received": 2,
        "items_reported": 4,
        "items_received": 4,
        "pagination_complete": True,
        "hit_result_limit": False,
        "inventory_scope_complete": True,
        "rule_version": "test-source-v1",
    }
    values.update(overrides)
    return SnapshotEvidence(**values)


def test_complete_requires_positive_explicit_proof() -> None:
    assessment = assess_snapshot(evidence())
    assert assessment.status is SnapshotStatus.COMPLETE
    assert assessment.rule_version == "test-source-v1"


def test_http_success_without_inventory_proof_is_unknown() -> None:
    assessment = assess_snapshot(
        evidence(
            inventory_scope_complete=None,
            pagination_complete=None,
            items_reported=None,
        )
    )
    assert assessment.status is SnapshotStatus.UNKNOWN
    assert "complete_inventory_not_proven" in assessment.reasons


def test_failures_truncation_and_count_mismatches_prevent_complete() -> None:
    cases = (
        evidence(requests_succeeded=1, requests_failed=1),
        evidence(pagination_complete=False),
        evidence(pages_received=1),
        evidence(items_received=3),
        evidence(hit_result_limit=True),
        evidence(inventory_scope_complete=False),
    )
    assert all(assess_snapshot(item).status is SnapshotStatus.INCOMPLETE for item in cases)


def test_source_runs_persist_execution_and_snapshot_state_separately() -> None:
    columns = SourceRun.__table__.columns
    assert "status" in columns
    assert {
        "snapshot_status",
        "trigger_type",
        "requests_attempted",
        "requests_succeeded",
        "requests_failed",
        "pages_expected",
        "pages_received",
        "items_reported",
        "items_received",
        "pagination_complete",
        "hit_result_limit",
        "inventory_scope_complete",
        "snapshot_reasons",
        "snapshot_evidence",
        "completeness_rule_version",
    } <= set(columns.keys())


def test_static_snapshot_flag_is_not_part_of_signal_adapter_contract() -> None:
    assert not hasattr(SourceAdapter, "snapshot_complete")
