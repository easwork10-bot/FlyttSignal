from flyttsignal.domains.events.models import EventType
from flyttsignal.domains.signals.inference import (
    RentalInferenceFacts,
    TurnoverEvidence,
    compare_rental_inference,
    infer_rental_signal,
)
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.timing import TimingFactType


def facts(
    *,
    new_construction: bool | None,
    tags: frozenset[str] = frozenset({"APARTMENT", "STANDARD_HOUSING"}),
    turnover_evidence: frozenset[TurnoverEvidence] = frozenset(),
) -> RentalInferenceFacts:
    return RentalInferenceFacts(
        event_type=EventType.RENTAL_LISTED,
        new_construction=new_construction,
        classification_tags=tags,
        turnover_evidence=turnover_evidence,
    )


def test_new_construction_listing_is_only_a_potential_future_move_in() -> None:
    decision = infer_rental_signal(facts(new_construction=True))

    assert decision.signal_type == SignalType.POTENTIAL_NEW_BUILD_MOVE_IN
    assert decision.reason_codes == ("RENTAL_LISTING_OBSERVED", "EXPLICIT_NEW_CONSTRUCTION")
    assert decision.timing_reference == TimingFactType.ADVERTISED_AVAILABLE_FROM


def test_false_construction_does_not_establish_turnover() -> None:
    decision = infer_rental_signal(facts(new_construction=False))

    assert decision.signal_type == SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE
    assert "EXPLICIT_NOT_NEW_CONSTRUCTION" in decision.reason_codes
    assert "TURNOVER_EVIDENCE_MISSING" in decision.reason_codes


def test_unknown_construction_remains_explicitly_unknown() -> None:
    decision = infer_rental_signal(facts(new_construction=None))

    assert decision.signal_type == SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE
    assert "CONSTRUCTION_STATUS_UNKNOWN" in decision.reason_codes
    assert "NEW_CONSTRUCTION_NOT_ESTABLISHED" in decision.warnings


def test_room_and_short_term_are_reasons_not_signal_types() -> None:
    decision = infer_rental_signal(
        facts(new_construction=None, tags=frozenset({"ROOM", "SHORT_TERM"}))
    )

    assert decision.signal_type == SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE
    assert "ROOM_LISTING" in decision.reason_codes
    assert "SHORT_TERM_CONTRACT" in decision.reason_codes


def test_turnover_requires_separate_evidence_and_stable_unit_identity() -> None:
    decision = infer_rental_signal(
        facts(
            new_construction=False,
            turnover_evidence=frozenset({TurnoverEvidence.LEASE_TERMINATION_OBSERVED}),
        )
    )

    assert decision.signal_type == SignalType.LIKELY_RENTAL_TURNOVER
    assert "LEASE_TERMINATION_OBSERVED" in decision.reason_codes
    assert "TURNOVER_EVIDENCE_MISSING" not in decision.reason_codes


def test_non_listing_event_has_no_rental_inference() -> None:
    decision = infer_rental_signal(
        RentalInferenceFacts(
            event_type=EventType.LISTING_REMOVED,
            new_construction=None,
            classification_tags=frozenset(),
        )
    )

    assert decision.signal_type is None
    assert decision.timing_reference is None


def test_current_product_query_excludes_superseded_signals() -> None:
    from flyttsignal.db.models import Signal
    from flyttsignal.db.repositories.dashboard import DashboardRepository

    assert "signals.superseded_at IS NULL" in str(
        DashboardRepository(None).signal_query(product_only=False)
    )
    assert "signals.superseded_at IS NULL" in str(Signal.current())


def test_derived_events_cannot_supply_factual_rental_inference() -> None:
    for event_type in (EventType.NEW_BUILD_MOVE_IN, EventType.SALE_SOLD):
        decision = infer_rental_signal(RentalInferenceFacts(event_type, None, frozenset()))
        assert decision.signal_type is None


def test_shadow_comparison_never_changes_the_legacy_decision() -> None:
    comparison = compare_rental_inference(
        legacy_signal_type=SignalType.LIKELY_TENANT_MOVE_OUT,
        facts=facts(new_construction=None),
    )

    assert comparison.legacy_signal_type == SignalType.LIKELY_TENANT_MOVE_OUT
    assert comparison.candidate.signal_type == SignalType.POTENTIAL_RENTAL_TENANCY_CHANGE
    assert comparison.differs is True
