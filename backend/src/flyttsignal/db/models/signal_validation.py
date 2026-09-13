import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
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
from flyttsignal.db.models.signals import Signal


class ValidationBatch(Base):
    __tablename__ = "validation_batches"
    __table_args__ = (
        CheckConstraint("status IN ('IN_REVIEW','COMPLETE')"),
        CheckConstraint("target_size > 0"),
        CheckConstraint("population_size >= target_size"),
        CheckConstraint(
            "(score_run_id IS NULL AND score_as_of_date IS NULL AND "
            "definition_set_hash IS NULL AND dimension_scope_key IS NULL) OR "
            "(score_run_id IS NOT NULL AND score_as_of_date IS NOT NULL AND "
            "definition_set_hash IS NOT NULL AND dimension_scope_key IS NOT NULL)",
            name="ck_validation_batches_dimension_provenance",
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    rule_version: Mapped[str] = mapped_column(String(50))
    seed: Mapped[str] = mapped_column(String(120))
    target_size: Mapped[int] = mapped_column(Integer)
    population_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="IN_REVIEW")
    selection_manifest: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    dimension_scope_key: Mapped[str | None] = mapped_column(String(100))
    score_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("score_runs.id", ondelete="RESTRICT")
    )
    score_as_of_date: Mapped[date | None] = mapped_column(Date)
    definition_set_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = now()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validations: Mapped[list["SignalValidation"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class SignalValidation(Base):
    __tablename__ = "signal_validations"
    __table_args__ = (
        UniqueConstraint("batch_id", "signal_id"),
        CheckConstraint("score_stratum IS NULL OR score_stratum IN ('LOW','MEDIUM','HIGH')"),
        CheckConstraint(
            "strength_stratum IS NULL OR strength_stratum IN ('LOW','MEDIUM','HIGH')"
        ),
        CheckConstraint(
            "(signal_strength_at_selection IS NULL AND data_confidence_at_selection IS NULL "
            "AND timing_at_selection IS NULL AND strength_stratum IS NULL) OR "
            "(signal_strength_at_selection IS NOT NULL AND "
            "data_confidence_at_selection IS NOT NULL "
            "AND timing_at_selection IS NOT NULL AND strength_stratum IS NOT NULL)",
            name="ck_signal_validations_dimension_snapshot",
        ),
        CheckConstraint(
            "signal_strength_at_selection IS NULL OR "
            "signal_strength_at_selection BETWEEN 0 AND 100"
        ),
        CheckConstraint(
            "data_confidence_at_selection IS NULL OR "
            "data_confidence_at_selection BETWEEN 0 AND 100"
        ),
        CheckConstraint(
            "timing_at_selection IS NULL OR timing_at_selection BETWEEN 0 AND 100"
        ),
        CheckConstraint("review_status IN ('PENDING','REVIEWED')"),
        CheckConstraint("verdict IS NULL OR verdict IN ('GOOD','QUESTIONABLE','BAD')"),
        CheckConstraint(
            "(review_status = 'PENDING' AND verdict IS NULL AND reviewed_at IS NULL) OR "
            "(review_status = 'REVIEWED' AND verdict IS NOT NULL AND reviewed_at IS NOT NULL)"
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("validation_batches.id", ondelete="CASCADE")
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    score_at_selection: Mapped[int | None] = mapped_column(Integer)
    score_stratum: Mapped[str | None] = mapped_column(String(20))
    signal_strength_at_selection: Mapped[int | None] = mapped_column(Integer)
    data_confidence_at_selection: Mapped[int | None] = mapped_column(Integer)
    timing_at_selection: Mapped[int | None] = mapped_column(Integer)
    strength_stratum: Mapped[str | None] = mapped_column(String(20))
    inclusion_reasons: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    source_keys: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    provider_keys: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    classification_tags: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    review_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    verdict: Mapped[str | None] = mapped_column(String(20))
    issue_codes: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    batch: Mapped[ValidationBatch] = relationship(back_populates="validations")
    signal: Mapped[Signal] = relationship()
