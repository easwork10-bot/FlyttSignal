import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flyttsignal.api.schemas.signals import SignalOut
from flyttsignal.domains.pilot.activity import PilotActivityType
from flyttsignal.domains.pilot.feedback import (
    PilotFeedbackReason,
    PilotFeedbackVerdict,
    reason_is_valid,
)


class PilotCohortCriteriaOut(BaseModel):
    city_id: int
    live_evidence_required: Literal[True] = True
    active_signals_only: Literal[True] = True
    dated_signals_only: Literal[True] = True
    signal_age_days: int
    move_horizon_days: int


class PilotSignalOut(SignalOut):
    strength_band: Literal["LOW", "MEDIUM", "HIGH"]
    signal_age_days: int
    days_until_window_start: int
    pilot_feedback: "PilotSignalFeedbackSummaryOut | None" = None


class PilotSignalFeedbackSummaryOut(BaseModel):
    verdict: PilotFeedbackVerdict
    reason: PilotFeedbackReason
    reviewed_at: datetime


class PilotSignalFiltersOut(BaseModel):
    address_query: str | None
    review_status: Literal["ALL", "REVIEWED", "UNREVIEWED"]
    strength_band: Literal["LOW", "MEDIUM", "HIGH"] | None
    signal_type: str | None
    date_from: date | None
    date_to: date | None
    property_type: str | None
    min_rooms: Decimal | None
    max_rooms: Decimal | None
    min_area_m2: Decimal | None
    max_area_m2: Decimal | None
    center_latitude: Decimal | None
    center_longitude: Decimal | None
    radius_km: Decimal | None


class PilotSignalSummaryOut(BaseModel):
    total: int
    high: int
    medium: int
    low: int
    next_30_days: int
    mapped: int


class PilotPaginationOut(BaseModel):
    limit: int
    offset: int
    has_previous: bool
    has_next: bool


class PilotSignalListOut(BaseModel):
    cohort_version: str
    cohort_as_of_date: date
    dimension_scope_key: str
    score_run_id: uuid.UUID
    score_as_of_date: date
    definition_set_hash: str
    criteria: PilotCohortCriteriaOut
    applied_filters: PilotSignalFiltersOut
    sort: Literal["PRIORITY", "MOVE_WINDOW", "NEWEST"]
    summary: PilotSignalSummaryOut
    pagination: PilotPaginationOut
    items: list[PilotSignalOut]
    count: int
    total: int


class PilotContextIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    pilot_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    cohort_version: str = Field(min_length=1, max_length=50)
    cohort_as_of_date: date
    dimension_scope_key: str = Field(min_length=1, max_length=100)
    score_run_id: uuid.UUID
    score_as_of_date: date
    definition_set_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class PilotFeedbackUpsert(PilotContextIn):
    verdict: PilotFeedbackVerdict
    reason: PilotFeedbackReason
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def verdict_supports_reason(self):
        if not reason_is_valid(self.verdict, self.reason):
            raise ValueError(f"{self.reason} is not valid for {self.verdict}")
        self.note = self.note or None
        return self


class PilotFeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    signal_id: uuid.UUID
    pilot_key: str
    cohort_version: str
    cohort_as_of_date: date
    dimension_scope_key: str
    score_run_id: uuid.UUID
    score_as_of_date: date
    definition_set_hash: str
    signal_strength_at_review: int
    data_confidence_at_review: int
    timing_at_review: int
    verdict: PilotFeedbackVerdict
    reason: PilotFeedbackReason
    note: str | None
    reviewed_at: datetime
    created_at: datetime
    updated_at: datetime


class PilotActivityUpsert(PilotContextIn):
    activity_type: PilotActivityType
    signal_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)

    @field_validator("signal_ids")
    @classmethod
    def unique_signal_ids(cls, signal_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(signal_ids)) != len(signal_ids):
            raise ValueError("signal_ids must be unique")
        return signal_ids


class PilotActivityRecordedOut(BaseModel):
    activity_type: PilotActivityType
    recorded_count: int


class PilotMetricsOut(BaseModel):
    pilot_key: str
    cohort_version: str
    cohort_as_of_date: date
    dimension_scope_key: str
    score_run_id: uuid.UUID
    score_as_of_date: date
    definition_set_hash: str
    shown: int
    opened: int
    reviewed: int
    useful: int
    maybe: int
    not_useful: int
    open_rate: float | None
    review_rate: float | None
    useful_rate: float | None
    reason_counts: dict[str, int]
