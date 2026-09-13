import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyttsignal.db.models.base import Base, now, uuid_pk
from flyttsignal.db.models.signals import Signal


class ScoreEvaluationRun(Base):
    __tablename__ = "score_evaluation_runs"
    __table_args__ = (
        CheckConstraint("status IN ('COMPLETE')"),
        CheckConstraint("population_size > 0"),
        UniqueConstraint("city_id", "candidate_rule_version", "input_fingerprint"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    baseline_rule_version: Mapped[str] = mapped_column(String(50))
    candidate_rule_version: Mapped[str] = mapped_column(String(50))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    as_of_date: Mapped[date] = mapped_column(Date)
    population_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETE")
    summary: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = now()
    evaluations: Mapped[list["SignalScoreEvaluation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SignalScoreEvaluation(Base):
    __tablename__ = "signal_score_evaluations"
    __table_args__ = (UniqueConstraint("run_id", "signal_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("score_evaluation_runs.id", ondelete="CASCADE")
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    baseline_score: Mapped[int] = mapped_column(Integer)
    candidate_score: Mapped[int] = mapped_column(Integer)
    delta: Mapped[int] = mapped_column(Integer)
    inputs: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    components: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = now()
    run: Mapped[ScoreEvaluationRun] = relationship(back_populates="evaluations")
    signal: Mapped[Signal] = relationship()


class SignalFeatureSnapshot(Base):
    """Immutable score input captured independently from any score rule."""

    __tablename__ = "signal_feature_snapshots"
    __table_args__ = (
        UniqueConstraint("signal_id", "feature_schema_revision", "as_of_date", "payload_hash"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), index=True
    )
    feature_schema_revision: Mapped[str] = mapped_column(String(80))
    as_of_date: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    payload_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = now()
    signal: Mapped[Signal] = relationship()


class ScoreDefinition(Base):
    """Immutable registered policy for one explainable score dimension."""

    __tablename__ = "score_definitions"
    __table_args__ = (
        CheckConstraint(
            "dimension IN ('SIGNAL_STRENGTH','DATA_CONFIDENCE','TIMING')",
            name="ck_score_definitions_dimension",
        ),
        CheckConstraint(
            "status IN ('CANDIDATE','ACTIVE','RETIRED')",
            name="ck_score_definitions_status",
        ),
        UniqueConstraint(
            "dimension",
            "definition_revision",
            "parameter_hash",
            "feature_schema_revision",
            "engine_revision",
            name="uq_score_definitions_identity",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    dimension: Mapped[str] = mapped_column(String(40))
    definition_revision: Mapped[str] = mapped_column(String(80))
    parameters: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    parameter_hash: Mapped[str] = mapped_column(String(64))
    feature_schema_revision: Mapped[str] = mapped_column(String(80))
    engine_revision: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="CANDIDATE")
    created_at: Mapped[datetime] = now()


class ScoreRun(Base):
    """One atomic, reproducible evaluation of a snapshot population."""

    __tablename__ = "score_runs"
    __table_args__ = (
        CheckConstraint("status IN ('COMPLETE')", name="ck_score_runs_status"),
        CheckConstraint("population_size > 0", name="ck_score_runs_population_size"),
        UniqueConstraint(
            "city_id",
            "as_of_date",
            "feature_schema_revision",
            "definition_set_hash",
            "population_fingerprint",
            name="uq_score_runs_replay_identity",
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    as_of_date: Mapped[date] = mapped_column(Date)
    feature_schema_revision: Mapped[str] = mapped_column(String(80))
    definition_set_hash: Mapped[str] = mapped_column(String(64))
    population_fingerprint: Mapped[str] = mapped_column(String(64))
    population_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETE")
    created_at: Mapped[datetime] = now()
    evaluations: Mapped[list["SignalDimensionEvaluation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SignalDimensionEvaluation(Base):
    """One dimension result tied to the exact definition and feature snapshot."""

    __tablename__ = "signal_dimension_evaluations"
    __table_args__ = (
        CheckConstraint(
            "dimension IN ('SIGNAL_STRENGTH','DATA_CONFIDENCE','TIMING')",
            name="ck_signal_dimension_evaluations_dimension",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_signal_dimension_evaluations_score",
        ),
        UniqueConstraint(
            "run_id",
            "signal_id",
            "dimension",
            name="uq_signal_dimension_evaluations_result",
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("score_runs.id", ondelete="CASCADE")
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE")
    )
    feature_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signal_feature_snapshots.id", ondelete="RESTRICT")
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("score_definitions.id", ondelete="RESTRICT")
    )
    dimension: Mapped[str] = mapped_column(String(40))
    score: Mapped[int] = mapped_column(Integer)
    components: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    warnings: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = now()
    run: Mapped[ScoreRun] = relationship(back_populates="evaluations")
    signal: Mapped[Signal] = relationship()
    feature_snapshot: Mapped[SignalFeatureSnapshot] = relationship()
    definition: Mapped[ScoreDefinition] = relationship()


class ScoreActivation(Base):
    """Reversible authority to serve selected definitions inside one bounded scope."""

    __tablename__ = "score_activations"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('INTERNAL_PILOT','CUSTOMER_PILOT','PRODUCTION')",
            name="ck_score_activations_scope_type",
        ),
        CheckConstraint(
            "dimension IN ('SIGNAL_STRENGTH','DATA_CONFIDENCE','TIMING')",
            name="ck_score_activations_dimension",
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= activated_at",
            name="ck_score_activations_retirement",
        ),
        Index(
            "uq_score_activations_active_scope_dimension",
            "scope_key",
            "city_id",
            "dimension",
            unique=True,
            postgresql_where=text("retired_at IS NULL"),
            sqlite_where=text("retired_at IS NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    scope_type: Mapped[str] = mapped_column(String(30))
    scope_key: Mapped[str] = mapped_column(String(100))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    dimension: Mapped[str] = mapped_column(String(40))
    definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("score_definitions.id", ondelete="RESTRICT")
    )
    decision_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("score_runs.id", ondelete="RESTRICT")
    )
    decision_reason: Mapped[str] = mapped_column(Text)
    activated_at: Mapped[datetime] = now()
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    definition: Mapped[ScoreDefinition] = relationship()
    decision_run: Mapped[ScoreRun] = relationship()
