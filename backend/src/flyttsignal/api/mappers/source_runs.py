from flyttsignal.api.schemas.sources import SourceRunOut
from flyttsignal.db.models import SourceRun


def source_run_out(run: SourceRun) -> SourceRunOut:
    return SourceRunOut(
        id=run.id,
        source_id=run.source_id,
        source_name=run.source.name,
        status=run.status.value,
        execution_status=run.status.value,
        trigger_type=run.trigger_type,
        snapshot_status=run.snapshot_status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        items_seen=run.items_seen,
        items_new=run.items_new,
        items_changed=run.items_changed,
        items_unchanged=run.items_unchanged,
        removal_candidates=run.removal_candidates,
        items_removed=run.items_removed,
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
        snapshot_reasons=run.snapshot_reasons,
        snapshot_evidence=run.snapshot_evidence,
        completeness_rule_version=run.completeness_rule_version,
        duration_ms=run.duration_ms,
        error_message=run.error_message,
    )
