from collections import Counter
from datetime import date
from itertools import combinations

from hypothesis import given, settings
from hypothesis import strategies as st

from flyttsignal.domains.signals.features import FEATURE_REGISTRY
from flyttsignal.domains.signals.snapshots import FeatureValueState
from flyttsignal.scoring.scenarios import (
    ScenarioFamily,
    baseline_features,
    pairwise_cover,
    scenario_catalog,
    scenario_catalog_fingerprint,
)

AS_OF = date(2026, 9, 2)


def test_catalog_covers_every_required_scenario_family() -> None:
    catalog = scenario_catalog()
    families = Counter(scenario.family for scenario in catalog)
    assert set(families) == set(ScenarioFamily)
    assert families[ScenarioFamily.DATE_BOUNDARY] >= 13
    assert families[ScenarioFamily.PAIRWISE] < 27
    assert len(catalog) >= 35


def test_every_scenario_is_complete_reproducible_and_concrete() -> None:
    expected_features = {feature.name for feature in FEATURE_REGISTRY}
    for scenario in scenario_catalog():
        first = scenario.snapshot(as_of_date=AS_OF)
        second = scenario.snapshot(as_of_date=AS_OF)
        assert set(first.features) == expected_features
        assert first.payload() == second.payload()
        assert first.fingerprint() == second.fingerprint()
        assert all(
            not (isinstance(value.value, dict) and "days_from_as_of" in value.value)
            for value in first.features.values()
        )


def test_date_boundaries_include_past_present_future_missing_and_invalid() -> None:
    scenarios = {scenario.key: scenario for scenario in scenario_catalog()}
    assert scenarios["available-minus-1-days"].snapshot(
        as_of_date=AS_OF
    ).features["days_until_available"].value == -1
    assert scenarios["available-plus-0-days"].snapshot(
        as_of_date=AS_OF
    ).features["available_from"].value == AS_OF
    assert scenarios["available-plus-730-days"].snapshot(
        as_of_date=AS_OF
    ).features["days_until_available"].value == 730
    assert (
        scenarios["available-date-missing"]
        .snapshot(as_of_date=AS_OF)
        .features["available_from"]
        .state
        is FeatureValueState.MISSING
    )
    invalid = scenarios["available-before-first-seen"].snapshot(as_of_date=AS_OF)
    assert invalid.features["lead_time_days"].state is FeatureValueState.MISSING


def test_pairwise_generator_covers_every_cross_axis_value_pair() -> None:
    axes = (("past", "near", "missing"), ("strong", "uncertain", "none"), ("active", "removed"))
    cases = pairwise_cover(axes)
    for left, right in combinations(range(len(axes)), 2):
        expected = {(a, b) for a in axes[left] for b in axes[right]}
        actual = {(case[left], case[right]) for case in cases}
        assert actual == expected


def test_commercial_variations_do_not_change_strength_inputs() -> None:
    baseline = baseline_features(AS_OF)
    commercial = {
        scenario.key: scenario.snapshot(as_of_date=AS_OF)
        for scenario in scenario_catalog()
        if "commercial_only" in scenario.invariants
    }
    assert set(commercial) == {"commercial-fields-missing", "large-expensive-home"}
    allowed = {"rooms", "area_m2", "monthly_rent"}
    for snapshot in commercial.values():
        changed = {
            name for name, value in snapshot.features.items() if value != baseline[name]
        }
        assert changed == allowed


def test_duplicate_rows_are_not_mislabeled_as_independent_evidence() -> None:
    scenario = next(
        item for item in scenario_catalog() if item.key == "duplicate-observations-one-provenance"
    )
    snapshot = scenario.snapshot(as_of_date=AS_OF)
    assert snapshot.features["evidence_count"].value == 3
    assert snapshot.features["independent_evidence_count"].value == 1


def test_conflicting_material_values_remain_explicit() -> None:
    scenario = next(item for item in scenario_catalog() if item.key == "conflicting-availability")
    snapshot = scenario.snapshot(as_of_date=AS_OF)
    available = snapshot.features["available_from"]
    assert available.state is FeatureValueState.CONFLICTING
    assert available.value == [date(2026, 10, 2), date(2026, 11, 1)]


@given(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)))
@settings(max_examples=40, deadline=None)
def test_catalog_fingerprint_is_deterministic_for_arbitrary_as_of(as_of_date: date) -> None:
    first = scenario_catalog_fingerprint(as_of_date=as_of_date)
    second = scenario_catalog_fingerprint(as_of_date=as_of_date)
    assert first == second
    assert len(first) == 64


@given(
    st.lists(
        st.lists(
            st.text(alphabet="abcd", min_size=1, max_size=3),
            min_size=1,
            max_size=4,
            unique=True,
        ),
        min_size=2,
        max_size=4,
    )
)
@settings(max_examples=60, deadline=None)
def test_pairwise_cover_property_for_generated_axes(axes: list[list[str]]) -> None:
    cases = pairwise_cover(axes)
    for left, right in combinations(range(len(axes)), 2):
        expected = {(a, b) for a in axes[left] for b in axes[right]}
        assert {(case[left], case[right]) for case in cases} == expected
