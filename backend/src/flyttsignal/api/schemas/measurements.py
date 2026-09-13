import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ListingMeasurementOut(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    metric: str
    value: Decimal | None
    unit: str
    status: str
    rule_version: str
    inputs: dict
    measured_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LeadTimeSummaryOut(BaseModel):
    source_key: str | None
    classification_tag: str | None
    listing_status: str | None
    rule_version: str
    generated_at: datetime
    population_count: int
    measurement_count: int
    measured_count: int
    missing_input_count: int
    invalid_input_count: int
    late_count: int
    min_days: Decimal | None
    median_days: Decimal | None
    max_days: Decimal | None
