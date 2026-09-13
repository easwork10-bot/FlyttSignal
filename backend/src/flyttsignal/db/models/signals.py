import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.events import Event
from flyttsignal.db.models.properties import Property
from flyttsignal.db.models.rental_listings import RentalListing
from flyttsignal.domains.signals.models import SignalType


class Signal(Base):
    @classmethod
    def current(cls):
        """Current inference only; historical readers deliberately omit this predicate."""
        return cls.superseded_at.is_(None)

    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("property_id", "signal_type"),
        CheckConstraint(
            "(superseded_at IS NULL AND superseded_by_signal_id IS NULL "
            "AND supersession_reason IS NULL) OR "
            "(superseded_at IS NOT NULL AND superseded_by_signal_id IS NOT NULL "
            "AND supersession_reason IS NOT NULL AND superseded_at >= created_at)",
            name="ck_signal_supersession_complete",
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType, name="signal_type"))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    # Preserved for pre-C7 audit history. Active consumers use dimension evaluations.
    legacy_score: Mapped[int | None] = mapped_column("score", Integer)
    estimated_move_from: Mapped[date | None] = mapped_column(Date)
    estimated_move_to: Mapped[date | None] = mapped_column(Date)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("signals.id")
    )
    supersession_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    property: Mapped[Property] = relationship()
    evidence: Mapped[list["SignalEvidence"]] = relationship(cascade="all, delete-orphan")
    legacy_score_components: Mapped[list["ScoreComponent"]] = relationship(
        cascade="all, delete-orphan"
    )
    outcomes: Mapped[list["SignalOutcome"]] = relationship(
        back_populates="signal", passive_deletes="all"
    )
    superseded_by_signal: Mapped["Signal | None"] = relationship(
        remote_side="Signal.id", foreign_keys=[superseded_by_signal_id]
    )


class SignalEvidence(Base):
    __tablename__ = "signal_evidence"
    __table_args__ = (
        CheckConstraint(
            "(superseded_at IS NULL AND superseded_by_event_id IS NULL "
            "AND supersession_reason IS NULL) OR "
            "(superseded_at IS NOT NULL AND superseded_by_event_id IS NOT NULL "
            "AND supersession_reason IS NOT NULL AND superseded_at >= valid_from)",
            name="ck_signal_evidence_supersession_complete",
        ),
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id"), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"), primary_key=True)
    weight: Mapped[int] = mapped_column(default=1)
    reason: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id"))
    supersession_reason: Mapped[str | None] = mapped_column(Text)
    event: Mapped[Event] = relationship(foreign_keys=[event_id])
    superseded_by_event: Mapped[Event | None] = relationship(
        foreign_keys=[superseded_by_event_id]
    )


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    __table_args__ = (
        UniqueConstraint("signal_id", "outcome_type", "dedupe_key", "rule_version"),
        CheckConstraint(
            "outcome_type IN ('LISTING_REMOVED','LISTING_RELISTED',"
            "'AVAILABLE_DATE_CHANGED','CROSS_SOURCE_CONFIRMED','UNKNOWN','CONFIRMED_MOVE')"
        ),
        CheckConstraint("subject IN ('LISTING','SIGNAL','HOUSEHOLD_MOVE')"),
        CheckConstraint("verification_level IN ('OBSERVED','CONFIRMED')"),
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
        CheckConstraint(
            "(outcome_type = 'CONFIRMED_MOVE' AND subject = 'HOUSEHOLD_MOVE' "
            "AND verification_level = 'CONFIRMED') OR "
            "(outcome_type != 'CONFIRMED_MOVE' AND subject != 'HOUSEHOLD_MOVE' "
            "AND verification_level = 'OBSERVED')"
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("signals.id", ondelete="SET NULL")
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rental_listings.id", ondelete="SET NULL")
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    outcome_type: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(30))
    verification_level: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    evidence: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    rule_version: Mapped[str] = mapped_column(String(50))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    signal: Mapped[Signal | None] = relationship(back_populates="outcomes")
    listing: Mapped[RentalListing | None] = relationship()
    event: Mapped[Event | None] = relationship()


class ScoreComponent(Base):
    """Historical pre-C7 FlyttScore explanation; never written by current ingestion."""

    __tablename__ = "score_components"
    id: Mapped[uuid.UUID] = uuid_pk()
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id"))
    component: Mapped[str] = mapped_column(String(100))
    points: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = now()
