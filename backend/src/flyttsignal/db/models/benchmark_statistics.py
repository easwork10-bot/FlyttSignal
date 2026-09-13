import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import RawItem, Source


class BenchmarkObservation(Base):
    __tablename__ = "benchmark_observations"
    __table_args__ = (
        UniqueConstraint("source_id", "dataset_key", "dimension_key", "metric_key", "period"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"))
    dataset_key: Mapped[str] = mapped_column(String(100))
    dimension_key: Mapped[str] = mapped_column(String(64))
    metric_key: Mapped[str] = mapped_column(String(100))
    municipality_code: Mapped[str] = mapped_column(String(4))
    period: Mapped[str] = mapped_column(String(30))
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str] = mapped_column(String(50))
    dimensions: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source: Mapped[Source] = relationship()
    raw_item: Mapped[RawItem] = relationship()
