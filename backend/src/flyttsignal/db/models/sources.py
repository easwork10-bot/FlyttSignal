import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, RunStatus, RunTrigger, Scope, SourceType, now, uuid_pk


class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    municipality_code: Mapped[str] = mapped_column(String(4), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = now()


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"))
    scope: Mapped[Scope] = mapped_column(Enum(Scope, name="source_scope"))
    access_method: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    poll_interval_minutes: Mapped[int] = mapped_column(default=1440)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SourceCity(Base):
    __tablename__ = "source_cities"
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SourceRun(Base):
    __tablename__ = "source_runs"
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status"))
    trigger_type: Mapped[str] = mapped_column(String(20), default=RunTrigger.UNKNOWN.value)
    started_at: Mapped[datetime] = now()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_seen: Mapped[int] = mapped_column(default=0)
    items_new: Mapped[int] = mapped_column(default=0)
    items_changed: Mapped[int] = mapped_column(default=0)
    items_unchanged: Mapped[int] = mapped_column(default=0)
    removal_candidates: Mapped[int] = mapped_column(default=0)
    items_removed: Mapped[int] = mapped_column(default=0)
    snapshot_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    requests_attempted: Mapped[int | None] = mapped_column(Integer)
    requests_succeeded: Mapped[int | None] = mapped_column(Integer)
    requests_failed: Mapped[int | None] = mapped_column(Integer)
    pages_expected: Mapped[int | None] = mapped_column(Integer)
    pages_received: Mapped[int | None] = mapped_column(Integer)
    items_reported: Mapped[int | None] = mapped_column(Integer)
    items_received: Mapped[int | None] = mapped_column(Integer)
    pagination_complete: Mapped[bool | None] = mapped_column(Boolean)
    hit_result_limit: Mapped[bool | None] = mapped_column(Boolean)
    inventory_scope_complete: Mapped[bool | None] = mapped_column(Boolean)
    snapshot_reasons: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list
    )
    snapshot_evidence: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict
    )
    completeness_rule_version: Mapped[str | None] = mapped_column(String(50))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    source: Mapped[Source] = relationship()


class RawItem(Base):
    __tablename__ = "raw_items"
    __table_args__ = (UniqueConstraint("source_id", "source_item_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    source_item_id: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = now()
    content_hash: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
