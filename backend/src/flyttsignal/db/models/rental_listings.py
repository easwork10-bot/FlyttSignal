import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.properties import Property
from flyttsignal.db.models.rental_developments import RentalProject
from flyttsignal.db.models.sources import RawItem, Source, SourceRun


class RentalListing(Base):
    """Current normalized listing state; RawItem remains the immutable provenance boundary."""

    __tablename__ = "rental_listings"
    __table_args__ = (
        Index(
            "uq_current_rental_listing_source_item",
            "source_id",
            "source_item_id",
            unique=True,
            postgresql_where=text("NOT is_historical"),
            sqlite_where=text("NOT is_historical"),
        ),
    )
    is_historical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"))
    raw_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_items.id"))
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    rental_project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rental_projects.id"))
    project_source_item_id: Mapped[str | None] = mapped_column(String(200))
    source_item_id: Mapped[str] = mapped_column(String(200))
    canonical_url: Mapped[str | None] = mapped_column(Text)
    upstream_provider_key: Mapped[str] = mapped_column(String(120))
    upstream_provider_name: Mapped[str] = mapped_column(String(200))
    unit_identifier: Mapped[str | None] = mapped_column(String(50))
    rooms: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    new_construction: Mapped[bool | None] = mapped_column(Boolean)
    monthly_rent: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    application_deadline: Mapped[date | None] = mapped_column(Date)
    available_from: Mapped[date | None] = mapped_column(Date)
    categories: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    data_mode: Mapped[str] = mapped_column(String(20))
    attribution: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = now()
    last_seen_at: Mapped[datetime] = now()
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source: Mapped[Source] = relationship()
    raw_item: Mapped[RawItem] = relationship()
    property: Mapped[Property] = relationship()
    rental_project: Mapped[RentalProject | None] = relationship()
    classifications: Mapped[list["RentalListingClassification"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    measurements: Mapped[list["ListingMeasurement"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    revisions: Mapped[list["RentalListingRevision"]] = relationship(
        back_populates="listing", order_by="RentalListingRevision.revision_number"
    )


class RentalListingRevision(Base):
    """Append-only normalized listing state valid from one explicit boundary."""

    __tablename__ = "rental_listing_revisions"
    __table_args__ = (
        UniqueConstraint("listing_id", "revision_number"),
        UniqueConstraint("listing_id", "operation_key"),
        CheckConstraint("revision_number > 0"),
        CheckConstraint("change_kind IN ('CONTENT_OBSERVED','LISTING_REMOVED','LISTING_RELISTED')"),
        CheckConstraint("provenance_kind IN ('DIRECT','RECONSTRUCTED')"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rental_listings.id"))
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_runs.id"))
    raw_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_items.id"))
    revision_number: Mapped[int] = mapped_column(Integer)
    operation_key: Mapped[str] = mapped_column(String(200))
    change_kind: Mapped[str] = mapped_column(String(30))
    provenance_kind: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    normalization_revision: Mapped[str] = mapped_column(String(80))
    normalized_payload_hash: Mapped[str] = mapped_column(String(64))
    listing_status: Mapped[str] = mapped_column(String(30))
    available_from: Mapped[date | None] = mapped_column(Date)
    application_deadline: Mapped[date | None] = mapped_column(Date)
    new_construction: Mapped[bool | None] = mapped_column(Boolean)
    categories: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    unit_identifier: Mapped[str | None] = mapped_column(String(50))
    extra_normalized_facts: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict
    )
    recorded_at: Mapped[datetime] = now()
    listing: Mapped[RentalListing] = relationship(back_populates="revisions")
    source_run: Mapped[SourceRun | None] = relationship()
    raw_item: Mapped[RawItem | None] = relationship()


class RentalListingClassification(Base):
    __tablename__ = "rental_listing_classifications"
    __table_args__ = (UniqueConstraint("listing_id", "tag", "rule_version"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rental_listings.id", ondelete="CASCADE")
    )
    tag: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    reason: Mapped[str] = mapped_column(String(100))
    evidence: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    rule_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    listing: Mapped[RentalListing] = relationship(back_populates="classifications")


class ListingMeasurement(Base):
    __tablename__ = "listing_measurements"
    __table_args__ = (
        UniqueConstraint("listing_id", "metric", "rule_version"),
        CheckConstraint("status IN ('MEASURED','MISSING_INPUT','INVALID_INPUT')"),
        CheckConstraint(
            "(status = 'MEASURED' AND value IS NOT NULL) OR "
            "(status != 'MEASURED' AND value IS NULL)"
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rental_listings.id", ondelete="CASCADE")
    )
    metric: Mapped[str] = mapped_column(String(50))
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    rule_version: Mapped[str] = mapped_column(String(50))
    inputs: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    measured_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    listing: Mapped[RentalListing] = relationship(back_populates="measurements")
