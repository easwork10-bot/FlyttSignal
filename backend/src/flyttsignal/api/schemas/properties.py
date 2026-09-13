import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RegisterUnitReferenceOut(BaseModel):
    external_register_unit_id: uuid.UUID
    designation: str
    register_unit_type: str


class AddressEnrichmentOut(BaseModel):
    source: str
    data_mode: str
    external_address_id: uuid.UUID
    canonical_address: str
    municipality_code: str
    postal_code: str | None
    postal_town: str | None
    status: str
    source_srid: int
    source_easting: Decimal
    source_northing: Decimal
    attribution: str
    observed_at: datetime
    updated_at: datetime
    register_unit: RegisterUnitReferenceOut | None = None


class PropertyOut(BaseModel):
    id: uuid.UUID
    address: str
    city_id: int
    city: str
    municipality_code: str
    property_type: str
    unit_identifier: str | None
    rooms: Decimal | None
    area_m2: Decimal | None
    new_construction: bool | None
    latitude: Decimal | None
    longitude: Decimal | None
    address_enrichments: list[AddressEnrichmentOut] = []
