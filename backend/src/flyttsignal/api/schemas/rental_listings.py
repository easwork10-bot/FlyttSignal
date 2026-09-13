import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from flyttsignal.api.schemas.properties import PropertyOut


class RentalListingOut(BaseModel):
    id: uuid.UUID
    source_item_id: str
    publisher: str
    upstream_provider_key: str
    upstream_provider_name: str
    unit_identifier: str | None
    rooms: Decimal | None
    area_m2: Decimal | None
    new_construction: bool | None
    canonical_url: str | None
    monthly_rent: Decimal | None
    application_deadline: date | None
    available_from: date | None
    categories: list[str]
    data_mode: str
    attribution: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    removed_at: datetime | None
    property: PropertyOut


class RentalListingList(BaseModel):
    items: list[RentalListingOut]
    count: int


class RentalListingClassificationOut(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    tag: str
    confidence: Decimal
    reason: str
    evidence: dict
    rule_version: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
