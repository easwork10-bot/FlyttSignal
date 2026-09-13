import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SignalOutcomeOut(BaseModel):
    id: uuid.UUID
    signal_id: uuid.UUID
    listing_id: uuid.UUID | None
    event_id: uuid.UUID | None
    outcome_type: str
    subject: str
    verification_level: str
    observed_at: datetime
    confidence: Decimal
    evidence: dict
    rule_version: str
    dedupe_key: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OutcomeSummaryItem(BaseModel):
    outcome_type: str
    subject: str
    verification_level: str
    count: int


class OutcomeSummaryOut(BaseModel):
    generated_at: datetime
    signal_population_count: int
    signals_with_outcomes: int
    outcome_count: int
    confirmed_move_count: int
    items: list[OutcomeSummaryItem]
