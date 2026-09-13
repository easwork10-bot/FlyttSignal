import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import RawItem, Source
from flyttsignal.domains.events.models import EventType


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index(
            "uq_current_event_raw_type",
            "raw_item_id",
            "event_type",
            unique=True,
            postgresql_where=text("NOT is_historical"),
            sqlite_where=text("NOT is_historical"),
        ),
    )
    is_historical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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
