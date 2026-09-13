import uuid
from datetime import UTC, date, datetime

from flyttsignal.domains.signals.outcomes import OUTCOME_DEFINITIONS
from flyttsignal.outcomes.service import (
    record_available_date_change,
    record_cross_source_outcome,
    record_signal_outcome,
)


class StubSession:
    def __init__(self, *, source_ids=(), observations=()):
        self.added = []
        self.source_ids = list(source_ids)
        self.observations = list(observations)

    def scalar(self, _query):
        return self.added[0] if self.added else None

    def scalars(self, _query):
        return self.source_ids

    def execute(self, _query):
        class Result:
            def __init__(self, rows):
                self.rows = rows

            def tuples(self):
                return iter(self.rows)

        return Result(self.observations)

    def add(self, row):
        self.added.append(row)


def test_outcome_definitions_separate_observation_from_confirmed_move() -> None:
    assert OUTCOME_DEFINITIONS["LISTING_REMOVED"].subject == "LISTING"
    assert OUTCOME_DEFINITIONS["LISTING_REMOVED"].verification_level == "OBSERVED"
    assert OUTCOME_DEFINITIONS["CONFIRMED_MOVE"].subject == "HOUSEHOLD_MOVE"
    assert OUTCOME_DEFINITIONS["CONFIRMED_MOVE"].verification_level == "CONFIRMED"


def test_record_signal_outcome_is_idempotent() -> None:
    session = StubSession()
    signal_id = uuid.uuid4()
    observed_at = datetime.now(UTC)

    first = record_signal_outcome(
        session,
        signal_id=signal_id,
        outcome_type="UNKNOWN",
        observed_at=observed_at,
        dedupe_key="same-evidence",
        evidence={"reason": "test"},
    )
    second = record_signal_outcome(
        session,
        signal_id=signal_id,
        outcome_type="UNKNOWN",
        observed_at=observed_at,
        dedupe_key="same-evidence",
        evidence={"reason": "test"},
    )

    assert first is second
    assert len(session.added) == 1


def test_unchanged_available_date_does_not_create_outcome() -> None:
    session = StubSession()

    count = record_available_date_change(
        session,
        listing=object(),
        previous=date(2026, 10, 1),
        current=date(2026, 10, 1),
        observed_at=datetime.now(UTC),
        run_id=uuid.uuid4(),
    )

    assert count == 0
    assert session.added == []


def test_cross_source_requires_two_distinct_publishers() -> None:
    session = StubSession(
        observations=[(uuid.uuid4(), "uppsalahem", "same-listing", uuid.uuid4())]
    )

    outcome = record_cross_source_outcome(
        session,
        signal_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )

    assert outcome is None
    assert session.added == []


def test_syndicated_same_provider_is_not_independent_evidence() -> None:
    session = StubSession(
        observations=[
            (uuid.uuid4(), "uppsalahem", "listing-1", uuid.uuid4()),
            (uuid.uuid4(), "uppsalahem", "listing-1", uuid.uuid4()),
        ]
    )

    outcome = record_cross_source_outcome(
        session,
        signal_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )

    assert outcome is None
    assert session.added == []


def test_distinct_canonical_providers_create_one_corroboration_outcome() -> None:
    session = StubSession(
        observations=[
            (uuid.uuid4(), "uppsalahem", "listing-1", uuid.uuid4()),
            (uuid.uuid4(), "rikshem", "listing-1", uuid.uuid4()),
        ]
    )

    outcome = record_cross_source_outcome(
        session,
        signal_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )

    assert outcome is session.added[0]
    assert outcome.evidence["canonical_provider_count"] == 2
