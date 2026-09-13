import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SignalValidationOut(BaseModel):
    id: uuid.UUID
    signal_id: uuid.UUID
    score_at_selection: int | None
    score_stratum: str | None
    signal_strength_at_selection: int | None
    data_confidence_at_selection: int | None
    timing_at_selection: int | None
    strength_stratum: str | None
    inclusion_reasons: list[str]
    source_keys: list[str]
    provider_keys: list[str]
    classification_tags: list[str]
    review_status: str
    verdict: str | None
    issue_codes: list[str]
    notes: str | None
    reviewer: str | None
    reviewed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class ValidationBatchSummaryOut(BaseModel):
    id: uuid.UUID
    name: str
    city_id: int
    rule_version: str
    dimension_scope_key: str | None
    score_run_id: uuid.UUID | None
    score_as_of_date: date | None
    definition_set_hash: str | None
    seed: str
    target_size: int
    population_size: int
    status: str
    reviewed_count: int
    pending_count: int
    verdict_counts: dict[str, int]
    issue_counts: dict[str, int]
    created_at: datetime
    completed_at: datetime | None


class ValidationBatchOut(ValidationBatchSummaryOut):
    selection_manifest: dict
    items: list[SignalValidationOut]
