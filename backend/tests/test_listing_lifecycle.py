import uuid
from datetime import UTC, datetime, timedelta

import pytest

from flyttsignal.db.models import RentalListing, RunStatus, RunTrigger, Source, SourceRun
from flyttsignal.domains.listings.lifecycle import ListingLifecyclePolicy
from flyttsignal.lifecycle.listings import apply_listing_lifecycle, mark_listing_seen

NOW = datetime(2026, 8, 29, 20, tzinfo=UTC)
SOURCE_ID = uuid.uuid4()
SOURCE_KEY = "uppsala_bostadsformedling_live_rentals"
RULE = "ubf-public-graphql-v2"
POLICY = ListingLifecyclePolicy(SOURCE_KEY, RULE, grace_runs=2)


def complete_run(age: int, *, trigger: RunTrigger = RunTrigger.SCHEDULED) -> SourceRun:
    started_at = NOW - timedelta(hours=age)
    return SourceRun(
        id=uuid.uuid4(),
        source_id=SOURCE_ID,
        status=RunStatus.SUCCESS,
        trigger_type=trigger.value,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        snapshot_status="COMPLETE",
        requests_attempted=1,
        requests_succeeded=1,
        requests_failed=0,
        pages_expected=1,
        pages_received=1,
        items_reported=10,
        items_received=10,
        pagination_complete=True,
        hit_result_limit=False,
        inventory_scope_complete=True,
        completeness_rule_version=RULE,
    )


def listing(source_item_id: str, *, misses: int = 0) -> RentalListing:
    return RentalListing(
        id=uuid.uuid4(),
        source_id=SOURCE_ID,
        source_item_id=source_item_id,
        data_mode="live",
        status="ACTIVE" if misses == 0 else "REMOVAL_CANDIDATE",
        consecutive_misses=misses,
    )


class StubSession:
    def __init__(self, prior_runs=(), listings=()):
        self.results = [list(prior_runs), list(listings)]
        self.calls = 0

    def scalars(self, _statement):
        result = self.results[self.calls]
        self.calls += 1
        return iter(result)

    def execute(self, _statement):
        class EmptyResult:
            @staticmethod
            def tuples():
                return []

        return EmptyResult()


def source() -> Source:
    return Source(id=SOURCE_ID, key=SOURCE_KEY, name="UBF")


def test_manual_run_is_blocked_before_any_database_query() -> None:
    session = StubSession()
    result = apply_listing_lifecycle(
        session,
        source=source(),
        current_run=complete_run(0, trigger=RunTrigger.MANUAL),
        observed_source_item_ids=set(),
        policy=POLICY,
    )

    assert result.applied is False
    assert result.reasons == ("current_run_not_scheduled",)
    assert session.calls == 0


def test_three_prior_runs_and_complete_current_run_create_first_candidate() -> None:
    missing = listing("missing")
    observed = listing("observed")
    session = StubSession(
        prior_runs=[complete_run(1), complete_run(2), complete_run(3)],
        listings=[missing, observed],
    )

    result = apply_listing_lifecycle(
        session,
        source=source(),
        current_run=complete_run(0),
        observed_source_item_ids={"observed"},
        policy=POLICY,
    )

    assert result.applied is True
    assert (result.candidates, result.removed) == (1, 0)
    assert (missing.status, missing.consecutive_misses) == ("REMOVAL_CANDIDATE", 1)
    assert (observed.status, observed.consecutive_misses) == ("ACTIVE", 0)


def test_second_eligible_miss_removes_without_touching_signal_data() -> None:
    missing = listing("missing", misses=1)
    session = StubSession(
        prior_runs=[complete_run(1), complete_run(2), complete_run(3)],
        listings=[missing],
    )
    current = complete_run(0)

    result = apply_listing_lifecycle(
        session,
        source=source(),
        current_run=current,
        observed_source_item_ids=set(),
        policy=POLICY,
    )

    assert (result.candidates, result.removed) == (0, 1)
    assert result.removed_listing_ids == (missing.id,)
    assert (missing.status, missing.consecutive_misses) == ("REMOVED", 2)
    assert missing.removed_at == current.completed_at


def test_insufficient_prior_readiness_makes_zero_listing_queries_or_writes() -> None:
    untouched = listing("missing")
    session = StubSession(prior_runs=[complete_run(1), complete_run(2)], listings=[untouched])

    result = apply_listing_lifecycle(
        session,
        source=source(),
        current_run=complete_run(0),
        observed_source_item_ids=set(),
        policy=POLICY,
    )

    assert result.applied is False
    assert session.calls == 1
    assert (untouched.status, untouched.consecutive_misses) == ("ACTIVE", 0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", RunStatus.FAILED),
        ("snapshot_status", "INCOMPLETE"),
        ("hit_result_limit", True),
        ("items_reported", 0),
        ("items_received", 0),
        ("completeness_rule_version", "ubf-public-graphql-v1"),
    ],
)
def test_unsafe_current_run_is_blocked_before_listing_queries(field, value) -> None:
    current = complete_run(0)
    setattr(current, field, value)
    session = StubSession()

    result = apply_listing_lifecycle(
        session,
        source=source(),
        current_run=current,
        observed_source_item_ids=set(),
        policy=POLICY,
    )

    assert result.applied is False
    assert session.calls == 0


def test_reappearance_restores_the_existing_listing() -> None:
    existing = listing("reappeared", misses=2)
    existing.status = "REMOVED"
    existing.removed_at = NOW - timedelta(hours=1)

    mark_listing_seen(existing, NOW)

    assert existing.status == "ACTIVE"
    assert existing.consecutive_misses == 0
    assert existing.removed_at is None
    assert existing.last_seen_at == NOW
