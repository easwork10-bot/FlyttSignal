from datetime import UTC, date, datetime
from decimal import Decimal

from flyttsignal.domains.events import EventType, event_type_for
from flyttsignal.domains.listings.lifecycle import listing_status_after_miss
from flyttsignal.domains.pilot.feedback import (
    PilotFeedbackReason,
    PilotFeedbackVerdict,
    reason_is_valid,
)
from flyttsignal.domains.properties.identity import PropertyIdentity
from flyttsignal.domains.properties.matching import (
    ONE_SIDED_UNIT_REASON,
    MatchStrength,
    PropertyFingerprint,
    choose_strong_match,
    classify_property_match,
    resolve_current_property_match,
)
from flyttsignal.domains.signals.inference import infer_signal_type
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.pilot import (
    PILOT_COHORT_VERSION,
    PilotCohortPolicy,
    days_until_window_start,
    signal_age_days,
)
from flyttsignal.ingestion.change_detection import classify_change, content_hash
from flyttsignal.normalization.service import normalize_item


def test_normalization() -> None:
    item = normalize_item(
        {
            "source_item_id": "one",
            "address": "  testgatan   12 ",
            "city": "uppsala",
            "area_m2": "74,5",
            "rooms": "3",
            "available_from": "2026-10-01",
        }
    )
    assert item.normalized_address == "Testgatan 12"
    assert item.city == "Uppsala"
    assert item.municipality_code == "0380"
    assert item.area_m2 == Decimal("74.5")


def test_strong_deduplication() -> None:
    incoming = fingerprint(area_m2=Decimal("74"))
    compatible = classify_property_match(incoming, fingerprint(area_m2=Decimal("74.5")))
    incompatible = classify_property_match(incoming, fingerprint(area_m2=Decimal("82")))
    assert compatible.strength == MatchStrength.STRONG_MATCH
    assert incompatible.strength == MatchStrength.NO_MATCH


def test_property_identity_serializes_decimal_facts_without_float_loss() -> None:
    identity = PropertyIdentity(
        unit_identifier="1201",
        rooms=Decimal("2.5"),
        area_m2=Decimal("74.50"),
        new_construction=False,
    )
    assert identity.as_dict() == {
        "unit_identifier": "1201",
        "rooms": "2.5",
        "area_m2": "74.50",
        "new_construction": False,
    }


def fingerprint(**overrides) -> PropertyFingerprint:
    values = {
        "normalized_address": "Testgatan 12",
        "city_id": 1,
        "property_type": "rental",
        "area_m2": Decimal("74"),
        "rooms": Decimal("3"),
        "unit_identifier": None,
    }
    values.update(overrides)
    return PropertyFingerprint(**values)


def test_matching_classifies_strong_uncertain_and_no_match() -> None:
    strong = classify_property_match(fingerprint(), fingerprint(area_m2=Decimal("74.5")))
    uncertain = classify_property_match(
        fingerprint(area_m2=None, rooms=None), fingerprint(area_m2=None, rooms=None)
    )
    different_unit = classify_property_match(
        fingerprint(unit_identifier="1201"), fingerprint(unit_identifier="1202")
    )
    assert strong.strength == MatchStrength.STRONG_MATCH
    assert uncertain.strength == MatchStrength.UNCERTAIN_MATCH
    assert different_unit.strength == MatchStrength.NO_MATCH


def test_uncertain_match_is_not_automatically_merged() -> None:
    candidate = object()
    found, decision = choose_strong_match(
        fingerprint(area_m2=None, rooms=None),
        [(candidate, fingerprint(area_m2=None, rooms=None))],
    )
    assert found is None
    assert decision.strength == MatchStrength.UNCERTAIN_MATCH


def test_one_sided_unit_identity_is_never_automatically_merged() -> None:
    for incoming, candidate in (
        (fingerprint(unit_identifier="B-1401"), fingerprint()),
        (fingerprint(), fingerprint(unit_identifier="B-1401")),
    ):
        found, decision = choose_strong_match(incoming, [(object(), candidate)])
        assert found is None
        assert decision.strength == MatchStrength.UNCERTAIN_MATCH
        assert "only one side" in decision.reason


def test_safely_separated_one_sided_identity_is_current_no_match() -> None:
    resolved = resolve_current_property_match(
        recorded_match=MatchStrength.UNCERTAIN_MATCH,
        recorded_reason=ONE_SIDED_UNIT_REASON,
        listing_unit_identifier="B-1401",
        property_unit_identifier="B-1401",
        ownership_consistent=True,
    )
    assert resolved == MatchStrength.NO_MATCH


def test_unresolved_or_differently_ambiguous_identity_stays_uncertain() -> None:
    cases = (
        {
            "recorded_reason": ONE_SIDED_UNIT_REASON,
            "property_unit_identifier": None,
            "ownership_consistent": True,
        },
        {
            "recorded_reason": ONE_SIDED_UNIT_REASON,
            "property_unit_identifier": "B-1401",
            "ownership_consistent": False,
        },
        {
            "recorded_reason": "Multiple strong candidates; automatic merge refused",
            "property_unit_identifier": "B-1401",
            "ownership_consistent": True,
        },
    )
    for case in cases:
        assert (
            resolve_current_property_match(
                recorded_match=MatchStrength.UNCERTAIN_MATCH,
                listing_unit_identifier="B-1401",
                **case,
            )
            == MatchStrength.UNCERTAIN_MATCH
        )


def test_multiple_strong_candidates_are_not_automatically_merged() -> None:
    found, decision = choose_strong_match(
        fingerprint(), [(object(), fingerprint()), (object(), fingerprint())]
    )
    assert found is None
    assert decision.strength == MatchStrength.UNCERTAIN_MATCH


def test_change_detection_is_order_independent() -> None:
    first = content_hash({"b": 2, "a": 1})
    second = content_hash({"a": 1, "b": 2})
    assert first == second
    assert classify_change(first, second) == "UNCHANGED"
    assert classify_change(None, first) == "NEW"
    assert classify_change(first, content_hash({"a": 2})) == "CHANGED"


def test_event_and_signal_generation() -> None:
    item = normalize_item({"source_item_id": "one", "address": "Testgatan 1", "city": "Uppsala"})
    event_type = event_type_for(new_construction=item.new_construction)
    assert event_type == EventType.RENTAL_LISTED
    assert infer_signal_type(event_type) == SignalType.LIKELY_TENANT_MOVE_OUT


def test_new_construction_maps_to_move_in_event() -> None:
    assert event_type_for(new_construction=True) == EventType.NEW_BUILD_MOVE_IN


def test_unknown_construction_remains_unknown_but_still_maps_to_listing_event() -> None:
    item = normalize_item(
        {
            "source_item_id": "unknown-construction",
            "address": "Okändgatan 1",
            "city": "Uppsala",
            "municipality_code": "0380",
        }
    )

    assert item.new_construction is None
    assert event_type_for(new_construction=item.new_construction) == EventType.RENTAL_LISTED


def test_rental_provenance_and_commercial_fields_normalize() -> None:
    item = normalize_item(
        {
            "source_item_id": "listing-one",
            "address": "Testgatan 1",
            "monthly_rent": "8 420".replace(" ", ""),
            "publisher_name": "Publiceringskanal",
            "upstream_provider_key": "hyresvard-one",
            "upstream_provider_name": "Hyresvärd One",
            "application_deadline": "2026-09-03",
            "categories": ["hyresrätt"],
        }
    )
    assert item.monthly_rent == Decimal("8420")
    assert item.upstream_provider_key == "hyresvard-one"
    assert item.application_deadline == date(2026, 9, 3)


def test_listing_removal_requires_two_complete_misses() -> None:
    assert listing_status_after_miss(1, 1) == "REMOVAL_CANDIDATE"
    assert listing_status_after_miss(2, 1) == "REMOVED"
    assert listing_status_after_miss(2, 3) == "REMOVAL_CANDIDATE"
    assert listing_status_after_miss(3, 3) == "REMOVED"


def test_pilot_cohort_v1_has_reproducible_time_boundaries() -> None:
    policy = PilotCohortPolicy()
    as_of = date(2026, 9, 1)

    assert policy.cohort_version == PILOT_COHORT_VERSION == "pilot-cohort-v1"
    assert policy.dimension_scope_key == "internal-pilot"
    assert policy.city_id == 1
    assert policy.created_from(as_of) == datetime(2026, 8, 4, tzinfo=UTC)
    assert policy.move_horizon_to(as_of) == date(2026, 11, 30)
    assert signal_age_days(datetime(2026, 8, 30, 12, tzinfo=UTC), as_of) == 2
    assert days_until_window_start(date(2026, 9, 20), as_of) == 19


def test_pilot_feedback_reasons_have_commercial_meaning() -> None:
    assert reason_is_valid(
        PilotFeedbackVerdict.USEFUL, PilotFeedbackReason.GOOD_OPPORTUNITY
    )
    assert reason_is_valid(
        PilotFeedbackVerdict.MAYBE, PilotFeedbackReason.INSUFFICIENT_CONTEXT
    )
    assert reason_is_valid(
        PilotFeedbackVerdict.NOT_USEFUL, PilotFeedbackReason.DUPLICATE
    )
    assert not reason_is_valid(
        PilotFeedbackVerdict.USEFUL, PilotFeedbackReason.WEAK_SIGNAL
    )
