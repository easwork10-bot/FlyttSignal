from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID


class TimingFactType(StrEnum):
    ADVERTISED_AVAILABLE_FROM = "ADVERTISED_AVAILABLE_FROM"
    APPLICATION_DEADLINE = "APPLICATION_DEADLINE"


class TimingState(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class TimingFact:
    fact_type: TimingFactType
    value: date | None
    observation_id: UUID


@dataclass(frozen=True)
class ResolvedTimingFact:
    fact_type: TimingFactType
    state: TimingState
    value: date | None
    observation_ids: tuple[UUID, ...]
    conflicting_values: tuple[date, ...] = ()
    warnings: tuple[str, ...] = ()


def resolve_timing_fact(
    facts: tuple[TimingFact, ...], *, fact_type: TimingFactType
) -> ResolvedTimingFact:
    """Resolve already-valid evidence without inventing a date or source precedence."""

    relevant = tuple(fact for fact in facts if fact.fact_type == fact_type)
    observation_ids = tuple(sorted((fact.observation_id for fact in relevant), key=str))
    dated = tuple(fact for fact in relevant if fact.value is not None)
    values = tuple(sorted({fact.value for fact in dated if fact.value is not None}))

    if not values:
        return ResolvedTimingFact(
            fact_type=fact_type,
            state=TimingState.MISSING,
            value=None,
            observation_ids=observation_ids,
        )
    if len(values) > 1:
        return ResolvedTimingFact(
            fact_type=fact_type,
            state=TimingState.CONFLICTING,
            value=None,
            observation_ids=observation_ids,
            conflicting_values=values,
            warnings=("CONFLICTING_TIMING_EVIDENCE",),
        )

    warnings = ("PARTIAL_TIMING_EVIDENCE",) if len(dated) != len(relevant) else ()
    return ResolvedTimingFact(
        fact_type=fact_type,
        state=TimingState.PRESENT,
        value=values[0],
        observation_ids=tuple(sorted((fact.observation_id for fact in dated), key=str)),
        warnings=warnings,
    )


def timing_not_applicable(fact_type: TimingFactType) -> ResolvedTimingFact:
    return ResolvedTimingFact(
        fact_type=fact_type,
        state=TimingState.NOT_APPLICABLE,
        value=None,
        observation_ids=(),
    )


def timing_unavailable(
    fact_type: TimingFactType, *, warning: str = "NO_PROVABLE_AS_OF_REVISION"
) -> ResolvedTimingFact:
    """Represent an unanswerable historical query without calling the fact missing."""

    return ResolvedTimingFact(
        fact_type=fact_type,
        state=TimingState.UNAVAILABLE,
        value=None,
        observation_ids=(),
        warnings=(warning,),
    )
