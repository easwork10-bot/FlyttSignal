import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import City, Source


class HousingProvider(Base):
    __tablename__ = "housing_providers"
    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    provider_type: Mapped[str] = mapped_column(String(30))
    official_url: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    cities: Mapped[list["HousingProviderCity"]] = relationship(back_populates="provider")
    channels: Mapped[list["ProviderChannel"]] = relationship(back_populates="provider")


class HousingProviderCity(Base):
    __tablename__ = "housing_provider_cities"
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("housing_providers.id"), primary_key=True
    )
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), primary_key=True)
    discovery_source: Mapped[str] = mapped_column(String(120))
    evidence_url: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider: Mapped[HousingProvider] = relationship(back_populates="cities")
    city: Mapped[City] = relationship()


class ProviderChannel(Base):
    __tablename__ = "provider_channels"
    __table_args__ = (UniqueConstraint("provider_id", "city_id", "channel_key"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("housing_providers.id"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    channel_key: Mapped[str] = mapped_column(String(160))
    channel_type: Mapped[str] = mapped_column(String(30))
    publisher_name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    coverage: Mapped[str] = mapped_column(String(20))
    collection_status: Mapped[str] = mapped_column(String(30))
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_agreement: Mapped[bool] = mapped_column(Boolean, default=False)
    next_action: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[HousingProvider] = relationship(back_populates="channels")
    city: Mapped[City] = relationship()
    source: Mapped[Source | None] = relationship()
