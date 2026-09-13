import uuid
from datetime import date, datetime

from pydantic import BaseModel

from flyttsignal.api.schemas.properties import PropertyOut


class EvidenceOut(BaseModel):
    event_id: uuid.UUID
    raw_item_id: uuid.UUID
    source_item_id: str
    event_type: str
    source: str
    observed_at: datetime
    effective_date: date | None
    weight: int
    reason: str


class ActiveDimensionsOut(BaseModel):
    run_id: uuid.UUID
    as_of_date: date
    definition_set_hash: str
    signal_strength: int
    data_confidence: int
    timing: int


class TimingFactOut(BaseModel):
    type: str
    state: str
    date: date | None
    observation_ids: list[uuid.UUID]
    conflicting_dates: list[date]
    warnings: list[str]


class SignalTimingOut(BaseModel):
    primary: TimingFactOut
    facts: list[TimingFactOut]
    mode: str
    as_of: datetime | None
    warnings: list[str]


class SignalOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    signal_type: str
    status: str
    active_dimensions: ActiveDimensionsOut
    timing: SignalTimingOut | None = None
    estimated_move_from: date | None
    estimated_move_to: date | None
    created_at: datetime
    updated_at: datetime
    property: PropertyOut
    evidence_count: int
    evidence: list[EvidenceOut] = []


class SignalList(BaseModel):
    items: list[SignalOut]
    count: int
