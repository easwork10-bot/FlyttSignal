from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator


class NormalizedItem(BaseModel):
    source_item_id: str
    address: str
    normalized_address: str
    city: str
    municipality_code: str
    rooms: Decimal | None = None
    area_m2: Decimal | None = None
    available_from: date | None = None
    property_type: str = "rental"
    unit_identifier: str | None = None
    new_construction: bool | None = None
    new_construction_observation_complete: bool = False
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    listed_at: date | None = None
    source_url: str | None = None
    publisher_name: str | None = None
    upstream_provider_key: str | None = None
    upstream_provider_name: str | None = None
    monthly_rent: Decimal | None = None
    application_deadline: date | None = None
    categories: list[str] = []
    data_mode: str = "fixture"
    attribution: str | None = None
    project_source_item_id: str | None = None

    @field_validator("rooms", "area_m2", "latitude", "longitude", "monthly_rent", mode="before")
    @classmethod
    def numeric(cls, value: object) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value).replace(",", "."))
        except InvalidOperation as exc:
            raise ValueError("must be numeric") from exc

    @field_validator("data_mode")
    @classmethod
    def supported_data_mode(cls, value: str) -> str:
        if value not in {"fixture", "live"}:
            raise ValueError("data_mode must be fixture or live")
        return value


def normalize_address(value: str) -> str:
    return " ".join(value.strip().split()).title()


def normalize_item(raw: dict) -> NormalizedItem:
    city = " ".join(str(raw.get("city", "Uppsala")).strip().split()).title()
    if city != "Uppsala":
        raise ValueError("Fake Uppsala adapter only accepts Uppsala items")
    address = " ".join(str(raw["address"]).strip().split())
    normalized = {
        **raw,
        "address": address,
        "normalized_address": normalize_address(address),
        "city": city,
        "municipality_code": str(raw.get("municipality_code") or "0380"),
        "property_type": str(raw.get("property_type") or "rental").lower(),
        "unit_identifier": (
            " ".join(str(raw["unit_identifier"]).strip().upper().split())
            if raw.get("unit_identifier")
            else None
        ),
    }
    return NormalizedItem.model_validate(normalized)
