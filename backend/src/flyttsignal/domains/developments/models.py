from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator


class RentalDevelopment(BaseModel):
    source_item_id: str
    source_url: str
    name: str
    upstream_provider_key: str
    upstream_provider_name: str
    address: str
    city: str
    municipality_code: str
    planned_unit_count: int | None = None
    active_listing_count: int
    rent_min: Decimal | None = None
    rent_max: Decimal | None = None
    rooms_min: Decimal | None = None
    rooms_max: Decimal | None = None
    area_min: Decimal | None = None
    area_max: Decimal | None = None
    available_from: date | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    status: str
    data_mode: str = "live"
    attribution: str

    @field_validator("data_mode")
    @classmethod
    def live_only(cls, value: str) -> str:
        if value != "live":
            raise ValueError("public rental projects must be live data")
        return value
