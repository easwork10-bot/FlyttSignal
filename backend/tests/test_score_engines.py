"""Behavioral contract for the candidate score dimensions."""

import runpy
from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest

from flyttsignal.domains.properties.matching import (
    MatchStrength,
    PropertyFingerprint,
    choose_strong_match,
)
from flyttsignal.domains.signals.engines.base import ScoreInput
from flyttsignal.domains.signals.engines.data_confidence import DataConfidenceEngine
from flyttsignal.domains.signals.engines.metadata import ScoreDimension
from flyttsignal.domains.signals.engines.signal_strength import (
    SignalStrengthEngine,
    SignalStrengthParameters,
)
from flyttsignal.domains.signals.engines.timing import TimingEngine
from flyttsignal.domains.signals.evaluation import (
    ScoreEvaluationService,
    create_evaluation_context,
)
from flyttsignal.domains.signals.snapshots import FeatureValue, FeatureValueState, present
from flyttsignal.scoring.scenarios import scenario_catalog

AS_OF = date(2026, 9, 2)


def _snapshot(key: str):
    scenario = next(item for item in scenario_catalog() if item.key == key)
    return scenario.snapshot(as_of_date=AS_OF)


def _evaluate(engine, key: str):
    return engine.evaluate(ScoreInput(snapshot=_snapshot(key), as_of=AS_OF))


def test_all_dimensions_are_deterministic_and_have_distinct_stable_definitions() -> None:
    service = ScoreEvaluationService()
    context = create_evaluation_context(as_of=AS_OF)
    snapshot = _snapshot("classification-apartment")

    first = service.evaluate_all_dimensions(snapshot, context)
    second = service.evaluate_all_dimensions(snapshot, context)

    assert first == second
    definition_ids = {metadata.definition_id for _, metadata in first.values()}
    assert len(definition_ids) == len(ScoreDimension)


def test_evaluation_date_must_match_the_snapshot() -> None:
    service = ScoreEvaluationService()
    context = create_evaluation_context(as_of=date(2026, 9, 3))

    with pytest.raises(ValueError, match="as_of"):
        service.evaluate_all_dimensions(_snapshot("classification-apartment"), context)


def test_parameter_change_changes_definition_identity_and_behavior() -> None:
    service = ScoreEvaluationService()
    context = create_evaluation_context(as_of=AS_OF)
    snapshot = _snapshot("classification-apartment")
    baseline, baseline_metadata = service.evaluate_dimension(
        snapshot, ScoreDimension.SIGNAL_STRENGTH, context
    )
    changed, changed_metadata = service.evaluate_dimension(
        snapshot,
        ScoreDimension.SIGNAL_STRENGTH,
        context,
        {"base_rental_listed_points": 50},
    )

    assert changed.score > baseline.score
    assert changed_metadata.definition_id != baseline_metadata.definition_id
    assert changed_metadata.parameter_hash != baseline_metadata.parameter_hash


def test_past_availability_never_receives_an_immediate_or_future_bonus() -> None:
    strength = _evaluate(SignalStrengthEngine(), "available-minus-1-days")
    timing = _evaluate(TimingEngine(), "available-minus-1-days")

    assert any(component.component == "effective_date_passed" for component in strength.components)
    assert any(component.component == "past_move" for component in timing.components)
    assert not any("future" in component.component for component in timing.components)
    assert not any(component.component == "immediate_move" for component in timing.components)


@pytest.mark.parametrize("key", ["unit-identifier-missing", "coordinates-missing"])
def test_explicit_false_quality_features_reduce_confidence_and_warn(key: str) -> None:
    engine = DataConfidenceEngine()
    baseline = _evaluate(engine, "classification-apartment")
    degraded = _evaluate(engine, key)

    assert degraded.score < baseline.score
    assert degraded.warnings


def test_missing_source_item_identity_reduces_confidence() -> None:
    engine = DataConfidenceEngine()
    baseline = _evaluate(engine, "classification-apartment")
    missing_identity = _evaluate(engine, "source-item-identity-missing")

    assert missing_identity.score < baseline.score
    assert any("source_item_id" in warning for warning in missing_identity.warnings)


@pytest.mark.parametrize("key", ["commercial-fields-missing", "large-expensive-home"])
def test_commercial_fields_cannot_change_signal_strength(key: str) -> None:
    engine = SignalStrengthEngine()
    baseline = _evaluate(engine, "classification-apartment")

    assert _evaluate(engine, key).score == baseline.score


def test_duplicate_rows_do_not_strengthen_but_independent_evidence_does() -> None:
    engine = SignalStrengthEngine()
    baseline = _evaluate(engine, "classification-apartment")
    duplicate = _evaluate(engine, "duplicate-observations-one-provenance")
    corroborated = _evaluate(engine, "independent-corroboration")

    assert duplicate.score == baseline.score
    assert corroborated.score > duplicate.score


def test_conflicting_availability_is_visible_and_gets_no_date_bonus() -> None:
    result = _evaluate(SignalStrengthEngine(), "conflicting-availability")

    assert any("conflicting" in warning for warning in result.warnings)
    assert not any(component.component == "known_effective_date" for component in result.components)


def test_removal_candidate_never_creates_timing_urgency() -> None:
    result = _evaluate(TimingEngine(), "listing-removal-candidate")

    assert any("no urgency" in warning for warning in result.warnings)
    assert not any(component.component == "removal_candidate" for component in result.components)


def test_signal_strength_uses_last_observation_not_signal_creation_age() -> None:
    engine = SignalStrengthEngine()
    baseline = _evaluate(engine, "signal-age-0-days")
    old_signal = _evaluate(engine, "signal-age-365-days")

    assert old_signal.score == baseline.score


def test_parameter_objects_reject_unknown_configuration() -> None:
    service = ScoreEvaluationService()
    with pytest.raises(TypeError):
        service.evaluate_dimension(
            _snapshot("classification-apartment"),
            ScoreDimension.SIGNAL_STRENGTH,
            create_evaluation_context(as_of=AS_OF),
            {"unknown_weight": 10},
        )


def test_score_is_always_bounded() -> None:
    result = SignalStrengthEngine(
        SignalStrengthParameters(base_rental_listed_points=500)
    ).evaluate(ScoreInput(snapshot=_snapshot("classification-apartment"), as_of=AS_OF))

    assert result.score == 100


def test_new_property_without_a_reusable_candidate_is_not_invalid_data() -> None:
    incoming = PropertyFingerprint("EXEMPELGATAN 1", 1, "APARTMENT", unit_identifier="1001")
    candidate, decision = choose_strong_match(incoming, [])
    assert candidate is None
    assert decision.strength is MatchStrength.NO_MATCH
    snapshot = _snapshot("classification-apartment")
    snapshot = replace(
        snapshot, features={**snapshot.features, "property_match": present(decision.strength.value)}
    )
    result = DataConfidenceEngine().evaluate(ScoreInput(snapshot, AS_OF))
    reuse = next(item for item in result.components if item.component == "property_not_reused")
    assert reuse.points == 0
    assert "validity is not assessed" in reuse.reason
    assert result.score == 30  # Only the other observed facts contribute.
    assert result.warnings


def test_uncertain_reuse_and_missing_unit_identity_keep_their_separate_penalties() -> None:
    engine = DataConfidenceEngine()
    strong = _evaluate(engine, "classification-apartment")
    no_reuse = _evaluate(engine, "no-property-match")
    uncertain = _evaluate(engine, "uncertain-property-match")
    no_unit = _evaluate(engine, "new-property-without-unit-identifier")
    assert uncertain.score < no_reuse.score < strong.score
    assert no_unit.score < no_reuse.score
    uncertain_component = next(
        c for c in uncertain.components if c.component == "uncertain_property_match"
    )
    unit_component = next(c for c in no_unit.components if c.component == "unit_identifier_missing")
    assert uncertain_component.points < 0
    assert unit_component.points < 0


@pytest.mark.parametrize("name", ["property_match", "unit_identifier_present"])
@pytest.mark.parametrize(
    "state",
    [FeatureValueState.MISSING, FeatureValueState.NOT_AVAILABLE, FeatureValueState.CONFLICTING],
)
def test_unknown_identity_features_cannot_improve_confidence(name, state) -> None:
    engine = DataConfidenceEngine()
    snapshot = _snapshot(
        "uncertain-property-match" if name == "property_match" else "unit-identifier-missing"
    )
    original = engine.evaluate(ScoreInput(snapshot, AS_OF))
    changed = replace(
        snapshot,
        features={**snapshot.features, name: FeatureValue(state, reason="not established")},
    )
    result = engine.evaluate(ScoreInput(changed, AS_OF))
    assert result.score <= original.score
    assert any(state.value.lower() in warning for warning in result.warnings)


def test_confidence_revision_changes_without_relabeling_other_dimensions() -> None:
    result = ScoreEvaluationService().evaluate_all_dimensions(
        _snapshot("classification-apartment"), create_evaluation_context(as_of=AS_OF)
    )
    assert result[ScoreDimension.SIGNAL_STRENGTH][1].definition_id == UUID(
        "13aeb3d0-f73f-5661-89f2-af75493f2947"
    )
    assert result[ScoreDimension.TIMING][1].definition_id == UUID(
        "8ee3e876-4a18-51a4-bbef-6e683e4a3666"
    )
    confidence = result[ScoreDimension.DATA_CONFIDENCE][1]
    assert confidence.definition_id != UUID("fafb4d8e-72ec-56cd-afa2-d02988e51f12")
    assert confidence.engine_revision == DataConfidenceEngine.revision


def test_scenario_gate_detects_reintroduced_no_match_penalty() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_candidate_engines.py"
    harness = runpy.run_path(str(script))
    report = harness["evaluate_scenarios"](AS_OF)
    assert report["invariant_failures"] == []
    result = report["scenarios"]["no-property-match"]["dimensions"]["DATA_CONFIDENCE"]
    next(c for c in result["components"] if c["component"] == "property_not_reused")["points"] = -50
    assert any(
        "must be neutral" in failure
        for failure in harness["validate_invariants"](report["scenarios"])
    )
