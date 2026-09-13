import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.sources import RawItem, Source


class SpatialFeature(Base):
    __tablename__ = "spatial_features"
    __table_args__ = (UniqueConstraint("source_id", "dataset_key", "source_item_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"))
    dataset_key: Mapped[str] = mapped_column(String(100))
    source_item_id: Mapped[str] = mapped_column(String(200))
    municipality_code: Mapped[str] = mapped_column(String(4))
    feature_type: Mapped[str] = mapped_column(String(50))
    subtype_code: Mapped[int] = mapped_column(Integer)
    subtype_label: Mapped[str] = mapped_column(String(100))
    status_code: Mapped[int] = mapped_column(Integer)
    status_label: Mapped[str] = mapped_column(String(100))
    activity_code: Mapped[int | None] = mapped_column(Integer)
    activity_label: Mapped[str | None] = mapped_column(String(100))
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geometry: Mapped[object] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False).with_variant(Text(), "sqlite")
    )
    attribution: Mapped[str] = mapped_column(Text)
    source_attributes: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    data_mode: Mapped[str] = mapped_column(String(20))
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source: Mapped[Source] = relationship()
    raw_item: Mapped[RawItem] = relationship()
