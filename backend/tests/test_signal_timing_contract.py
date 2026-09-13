import uuid
from datetime import date

from flyttsignal.domains.signals.timing import (
    ResolvedTimingFact,
    TimingFact,
    TimingFactType,
    TimingState,
    resolve_timing_fact,
    timing_not_applicable,
    timing_unavailable,
)

AVAILABLE = TimingFactType.ADVERTISED_AVAILABLE_FROM


def fact(value: date | None, *, identifier: int) -> TimingFact:
    return TimingFact(AVAILABLE, value, uuid.UUID(int=identifier))


def test_missing_timing_is_not_replaced_with_a_default_date() -> None:
    resolved = resolve_timing_fact((fact(None, identifier=1),), fact_type=AVAILABLE)

    assert resolved.state == TimingState.MISSING
    assert resolved.value is None


def test_matching_observations_resolve_to_one_provenanced_fact() -> None:
    advertised = date(2026, 10, 1)
    resolved = resolve_timing_fact(
        (fact(advertised, identifier=2), fact(advertised, identifier=1)),
        fact_type=AVAILABLE,
    )

    assert resolved.state == TimingState.PRESENT
    assert resolved.value == advertised
    assert resolved.observation_ids == (uuid.UUID(int=1), uuid.UUID(int=2))
    assert resolved.warnings == ()


def test_partial_timing_evidence_remains_visible() -> None:
    resolved = resolve_timing_fact(
        (fact(date(2026, 10, 1), identifier=1), fact(None, identifier=2)),
        fact_type=AVAILABLE,
    )

    assert resolved.state == TimingState.PRESENT
    assert resolved.warnings == ("PARTIAL_TIMING_EVIDENCE",)
    assert resolved.observation_ids == (uuid.UUID(int=1),)


def test_conflicting_dates_are_not_silently_prioritized() -> None:
    resolved = resolve_timing_fact(
        (fact(date(2026, 10, 15), identifier=2), fact(date(2026, 10, 1), identifier=1)),
        fact_type=AVAILABLE,
    )

    assert resolved.state == TimingState.CONFLICTING
    assert resolved.value is None
    assert resolved.conflicting_values == (date(2026, 10, 1), date(2026, 10, 15))
    assert resolved.warnings == ("CONFLICTING_TIMING_EVIDENCE",)


def test_other_fact_types_do_not_contaminate_the_primary_anchor() -> None:
    deadline = TimingFact(
        TimingFactType.APPLICATION_DEADLINE,
        date(2026, 9, 15),
        uuid.UUID(int=2),
    )
    resolved = resolve_timing_fact(
        (fact(date(2026, 10, 1), identifier=1), deadline),
        fact_type=AVAILABLE,
    )

    assert resolved.state == TimingState.PRESENT
    assert resolved.value == date(2026, 10, 1)
    assert resolved.observation_ids == (uuid.UUID(int=1),)


def test_not_applicable_is_distinct_from_missing() -> None:
    resolved: ResolvedTimingFact = timing_not_applicable(AVAILABLE)

    assert resolved.state == TimingState.NOT_APPLICABLE
    assert resolved.value is None


def test_unavailable_is_distinct_from_missing_and_not_applicable() -> None:
    resolved = timing_unavailable(AVAILABLE)

    assert resolved.state == TimingState.UNAVAILABLE
    assert resolved.value is None
    assert resolved.warnings == ("NO_PROVABLE_AS_OF_REVISION",)
