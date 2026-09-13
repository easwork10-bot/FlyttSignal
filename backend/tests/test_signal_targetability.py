from flyttsignal.domains.signals.inference import RentalInferenceFacts
from flyttsignal.domains.signals.targetability import (
    Targetability,
    TargetabilityFacts,
    decide_targetability,
)


def test_stable_unit_identity_allows_unit_precision() -> None:
    decision = decide_targetability(
        TargetabilityFacts(True, True, True)
    )

    assert decision.level == Targetability.UNIT
    assert decision.reason_codes == ("STABLE_UNIT_IDENTITY",)


def test_building_and_area_are_distinct_fallback_levels() -> None:
    building = decide_targetability(TargetabilityFacts(False, True, True))
    area = decide_targetability(TargetabilityFacts(False, False, True))

    assert building.level == Targetability.BUILDING
    assert area.level == Targetability.AREA


def test_identity_conflict_fails_closed_even_when_identifiers_exist() -> None:
    decision = decide_targetability(
        TargetabilityFacts(True, True, True, identity_conflict=True)
    )

    assert decision.level == Targetability.NONE
    assert decision.reason_codes == ("IDENTITY_CONFLICT",)


def test_targetability_is_not_an_input_to_rental_signal_inference() -> None:
    from inspect import signature

    parameters = signature(RentalInferenceFacts).parameters
    assert "targetability" not in parameters
