import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import City, RawItem, Source


class AddressEnrichment(Base):
    __tablename__ = "address_enrichments"
    __table_args__ = (
        UniqueConstraint("source_id", "address_id"),
        UniqueConstraint("source_id", "external_address_id"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"))
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"))
    external_address_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    canonical_address: Mapped[str] = mapped_column(String(250))
    municipality_code: Mapped[str] = mapped_column(String(4))
    postal_code: Mapped[str | None] = mapped_column(String(5))
    postal_town: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    source_srid: Mapped[int] = mapped_column(Integer)
    source_easting: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    source_northing: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    attribution: Mapped[str] = mapped_column(Text)
    source_attributes: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    observed_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source: Mapped[Source] = relationship()
    raw_item: Mapped[RawItem] = relationship()
    address: Mapped["Address"] = relationship(back_populates="enrichments")
    register_unit_link: Mapped["AddressRegisterUnitLink | None"] = relationship(
        back_populates="address_enrichment",
        cascade="all, delete-orphan",
        uselist=False,
    )


class AddressRegisterUnitLink(Base):
    __tablename__ = "address_register_unit_links"
    __table_args__ = (UniqueConstraint("address_enrichment_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    address_enrichment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("address_enrichments.id", ondelete="CASCADE")
    )
    external_register_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    designation: Mapped[str] = mapped_column(String(250))
    register_unit_type: Mapped[str] = mapped_column(String(30))
    observed_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    address_enrichment: Mapped[AddressEnrichment] = relationship(
        back_populates="register_unit_link"
    )


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (UniqueConstraint("normalized_address", "city_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    raw_address: Mapped[str] = mapped_column(String(250))
    normalized_address: Mapped[str] = mapped_column(String(250))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    municipality_code: Mapped[str] = mapped_column(String(4))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    geometry: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326))
    created_at: Mapped[datetime] = now()
    city: Mapped[City] = relationship()
    enrichments: Mapped[list["AddressEnrichment"]] = relationship(back_populates="address")


class Property(Base):
    __tablename__ = "properties"
    id: Mapped[uuid.UUID] = uuid_pk()
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id"))
    property_type: Mapped[str] = mapped_column(String(50))
    unit_identifier: Mapped[str | None] = mapped_column(String(50))
    rooms: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    new_construction: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    address: Mapped[Address] = relationship()
