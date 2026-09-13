import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import RawItem, Source


class RentalProject(Base):
    """A development/project card; it is context and must not emit listing events."""

    __tablename__ = "rental_projects"
    __table_args__ = (UniqueConstraint("source_id", "source_item_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"), unique=True)
    source_item_id: Mapped[str] = mapped_column(String(200))
    canonical_url: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(200))
    upstream_provider_key: Mapped[str] = mapped_column(String(120))
    upstream_provider_name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(100))
    municipality_code: Mapped[str] = mapped_column(String(4))
    planned_unit_count: Mapped[int | None] = mapped_column(Integer)
    active_listing_count: Mapped[int] = mapped_column(Integer, default=0)
    rent_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rent_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rooms_min: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    rooms_max: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    area_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    area_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    available_from: Mapped[date | None] = mapped_column(Date)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    status: Mapped[str] = mapped_column(String(30))
    data_mode: Mapped[str] = mapped_column(String(20))
    attribution: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = now()
    last_seen_at: Mapped[datetime] = now()
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source: Mapped[Source] = relationship()
    raw_item: Mapped[RawItem] = relationship()
