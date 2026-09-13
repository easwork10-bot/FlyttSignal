import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import RawItem, Source
from flyttsignal.domains.events.models import EventType


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("raw_item_id", "event_type"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"))
    upstream_provider_key: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type"))
    observed_at: Mapped[datetime] = now()
    effective_date: Mapped[date | None] = mapped_column(Date)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = now()
    source: Mapped[Source] = relationship()
    raw_item: Mapped[RawItem] = relationship()
