import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.signals import Signal


class PilotSignalFeedback(Base):
    __tablename__ = "pilot_signal_feedback"
    __table_args__ = (
        UniqueConstraint(
            "pilot_key",
            "signal_id",
            "cohort_version",
            "score_rule_version",
            "cohort_as_of_date",
        ),
        CheckConstraint("verdict IN ('USEFUL','MAYBE','NOT_USEFUL')"),
        CheckConstraint(
            "reason IN ('GOOD_OPPORTUNITY','TOO_EARLY','TOO_LATE','WRONG_PROPERTY',"
            "'WEAK_SIGNAL','DUPLICATE','OUTSIDE_SERVICE_AREA','INSUFFICIENT_CONTEXT')"
        ),
        CheckConstraint("score_at_review >= 0 AND score_at_review <= 100"),
        CheckConstraint(
            "(score_rule_version IS NOT NULL AND score_at_review IS NOT NULL AND "
            "dimension_scope_key IS NULL AND score_run_id IS NULL AND "
            "score_as_of_date IS NULL AND definition_set_hash IS NULL AND "
            "signal_strength_at_review IS NULL AND data_confidence_at_review IS NULL AND "
            "timing_at_review IS NULL) OR "
            "(score_rule_version IS NULL AND score_at_review IS NULL AND "
            "dimension_scope_key IS NOT NULL AND score_run_id IS NOT NULL AND "
            "score_as_of_date IS NOT NULL AND definition_set_hash IS NOT NULL AND "
            "signal_strength_at_review IS NOT NULL AND data_confidence_at_review IS NOT NULL AND "
            "timing_at_review IS NOT NULL)",
            name="ck_pilot_feedback_snapshot_mode",
        ),
        CheckConstraint(
            "signal_strength_at_review IS NULL OR signal_strength_at_review BETWEEN 0 AND 100",
            name="ck_pilot_feedback_strength_range",
        ),
        CheckConstraint(
            "data_confidence_at_review IS NULL OR data_confidence_at_review BETWEEN 0 AND 100",
            name="ck_pilot_feedback_confidence_range",
        ),
        CheckConstraint(
            "timing_at_review IS NULL OR timing_at_review BETWEEN 0 AND 100",
            name="ck_pilot_feedback_timing_range",
        ),
        Index(
            "uq_pilot_feedback_dimension_snapshot",
            "pilot_key",
            "signal_id",
            "cohort_version",
            "dimension_scope_key",
            "score_run_id",
            "cohort_as_of_date",
            unique=True,
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), index=True
    )
    pilot_key: Mapped[str] = mapped_column(String(80))
    cohort_version: Mapped[str] = mapped_column(String(50))
    score_rule_version: Mapped[str | None] = mapped_column(String(50))
    cohort_as_of_date: Mapped[date] = mapped_column(Date)
    score_at_review: Mapped[int | None] = mapped_column(Integer)
    dimension_scope_key: Mapped[str | None] = mapped_column(String(100))
    score_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("score_runs.id", ondelete="RESTRICT")
    )
    score_as_of_date: Mapped[date | None] = mapped_column(Date)
    definition_set_hash: Mapped[str | None] = mapped_column(String(64))
    signal_strength_at_review: Mapped[int | None] = mapped_column(Integer)
    data_confidence_at_review: Mapped[int | None] = mapped_column(Integer)
    timing_at_review: Mapped[int | None] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    signal: Mapped[Signal] = relationship()
