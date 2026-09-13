import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    source_type: str
    scope: str
    access_method: str
    enabled: bool
    status: str
    last_run_at: datetime | None
    last_success_at: datetime | None
    next_run_at: datetime | None
    poll_interval_minutes: int
    model_config = ConfigDict(from_attributes=True)


class SourceRunOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    status: str
    execution_status: str
    trigger_type: str
    snapshot_status: str
    started_at: datetime
    completed_at: datetime | None
    items_seen: int
    items_new: int
    items_changed: int
    items_unchanged: int
    removal_candidates: int
    items_removed: int
    requests_attempted: int | None
    requests_succeeded: int | None
    requests_failed: int | None
    pages_expected: int | None
    pages_received: int | None
    items_reported: int | None
    items_received: int | None
    pagination_complete: bool | None
    hit_result_limit: bool | None
    inventory_scope_complete: bool | None
    snapshot_reasons: list[str]
    snapshot_evidence: dict
    completeness_rule_version: str | None
    duration_ms: int | None
    error_message: str | None


class LifecycleReadinessOut(BaseModel):
    source_key: str
    status: str
    required_runs: int
    qualifying_runs: int
    rule_version: str | None
    reasons: list[str]
    considered_run_ids: list[uuid.UUID]
    latest_scheduled_run_at: datetime | None
    evaluated_at: datetime
