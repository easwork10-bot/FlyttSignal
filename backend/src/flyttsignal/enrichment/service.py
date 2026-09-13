from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


class RegisterUnitReferenceInput(BaseModel):
    external_register_unit_id: UUID
    designation: str
    register_unit_type: Literal["Fastighet", "Samfällighet"]


class AddressEnrichmentInput(BaseModel):
    target_address_id: UUID
    external_address_id: UUID
    canonical_address: str
    normalized_address: str
    municipality_code: str
    postal_code: str | None = None
    postal_town: str | None = None
    status: str
    source_srid: int
    source_easting: Decimal
    source_northing: Decimal
    attribution: str
    source_attributes: dict
    register_unit_reference: RegisterUnitReferenceInput | None = None

    @field_validator("source_easting", "source_northing", mode="before")
    @classmethod
    def numeric(cls, value: object) -> Decimal:
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("must be numeric") from exc
