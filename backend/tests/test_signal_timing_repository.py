import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

from flyttsignal.db.repositories.signal_timing import SignalTimingRepository
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.resolved_timing import TimingReadMode
from flyttsignal.domains.signals.timing import TimingFactType, TimingState


class StubScalarResult:
    def __init__(self, values):
        self.values = values

    def __iter__(self):
        return iter(self.values)


class StubSession:
    def __init__(self, *, links=(), revisions=()):
        self.links = links
        self.revisions = revisions

    def execute(self, _query):
        return self.links

    def scalars(self, _query):
        return StubScalarResult(self.revisions)


def listing(*, status="ACTIVE", available_from=None, application_deadline=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        raw_item_id=uuid.uuid4(),
        status=status,
        available_from=available_from,
        application_deadline=application_deadline,
    )


def revision(
    rental_listing,
    *,
    number=1,
    status="ACTIVE",
    available_from=None,
    application_deadline=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        listing_id=rental_listing.id,
        revision_number=number,
        valid_from=datetime(2026, 9, number, tzinfo=UTC),
        listing_status=status,
        available_from=available_from,
        application_deadline=application_deadline,
    )


def fact(result, fact_type):
    return next(item for item in result.facts if item.fact_type == fact_type)


def test_current_read_uses_latest_append_only_revision() -> None:
    signal_id = uuid.uuid4()
    item = listing(available_from=date(2030, 1, 1))
    older = revision(item, number=1, available_from=date(2026, 10, 1))
    latest = revision(
        item,
        number=2,
        available_from=date(2026, 11, 1),
        application_deadline=date(2026, 10, 15),
    )
    repository = SignalTimingRepository(
        StubSession(links=((signal_id, item),), revisions=(latest, older))  # type: ignore[arg-type]
    )

    result = repository.current_for_signals(
        {signal_id: SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE}
    )[signal_id]

    assert result.mode == TimingReadMode.CURRENT
    assert result.primary.value == date(2026, 11, 1)
    assert result.primary.observation_ids == (latest.id,)
    assert fact(result, TimingFactType.APPLICATION_DEADLINE).value == date(2026, 10, 15)
    assert result.warnings == ()


def test_current_read_has_explicit_projection_fallback_during_cutover() -> None:
    signal_id = uuid.uuid4()
    item = listing(available_from=date(2026, 10, 1))
    repository = SignalTimingRepository(
        StubSession(links=((signal_id, item),))  # type: ignore[arg-type]
    )

    result = repository.current_for_signals(
        {signal_id: SignalType.LIKELY_TENANT_MOVE_OUT}
    )[signal_id]

    assert result.primary.state == TimingState.PRESENT
    assert result.primary.observation_ids == (item.raw_item_id,)
    assert result.warnings == ("CURRENT_PROJECTION_FALLBACK",)


def test_historical_read_never_falls_back_to_mutable_current_projection() -> None:
    signal_id = uuid.uuid4()
    item = listing(available_from=date(2026, 10, 1))
    repository = SignalTimingRepository(
        StubSession(links=((signal_id, item),))  # type: ignore[arg-type]
    )

    result = repository.as_of_for_signals(
        {signal_id: SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE},
        as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )[signal_id]

    assert result.mode == TimingReadMode.AS_OF
    assert result.primary.state == TimingState.UNAVAILABLE
    assert result.primary.value is None
    assert result.warnings == ("NO_PROVABLE_AS_OF_REVISION",)


def test_removed_revision_has_no_current_actionable_timing() -> None:
    signal_id = uuid.uuid4()
    item = listing()
    removed = revision(item, status="REMOVED", available_from=date(2026, 10, 1))
    repository = SignalTimingRepository(
        StubSession(links=((signal_id, item),), revisions=(removed,))  # type: ignore[arg-type]
    )

    result = repository.current_for_signals(
        {signal_id: SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE}
    )[signal_id]

    assert result.primary.state == TimingState.MISSING
    assert result.primary.value is None
    assert result.warnings == ("LISTING_NOT_ACTIVE",)


def test_non_rental_signal_timing_is_not_applicable_without_queries() -> None:
    signal_id = uuid.uuid4()
    result = SignalTimingRepository(StubSession()).current_for_signals(  # type: ignore[arg-type]
        {signal_id: SignalType.LIKELY_HOMEOWNER_MOVE}
    )[signal_id]

    assert result.primary.state == TimingState.NOT_APPLICABLE
