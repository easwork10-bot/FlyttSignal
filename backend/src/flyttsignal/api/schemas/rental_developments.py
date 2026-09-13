import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class RentalProjectOut(BaseModel):
    id: uuid.UUID
    source_item_id: str
    name: str
    canonical_url: str
    upstream_provider_key: str
    upstream_provider_name: str
    address: str
    city: str
    planned_unit_count: int | None
    active_listing_count: int
    imported_listing_count: int
    rent_min: Decimal | None
    rent_max: Decimal | None
    rooms_min: Decimal | None
    rooms_max: Decimal | None
    area_min: Decimal | None
    area_max: Decimal | None
    available_from: date | None
    status: str
    data_mode: str
    attribution: str
    last_seen_at: datetime


class RentalProjectList(BaseModel):
    items: list[RentalProjectOut]
    count: int
