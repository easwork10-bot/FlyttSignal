"""Deterministic scenario catalog for signal-engine evaluation."""

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from hashlib import sha256
from itertools import combinations, product
from uuid import UUID, uuid5

from flyttsignal.domains.signals.features import FEATURES_BY_NAME
from flyttsignal.domains.signals.snapshots import (
    FEATURE_SCHEMA_REVISION,
    FeatureSnapshot,
    FeatureValue,
    FeatureValueState,
    missing,
    present,
    unavailable,
)

SCENARIO_NAMESPACE = UUID("9fbc8899-933c-4ccc-92ee-5e8cf37635f5")
SOURCE_ID = UUID("2b405ed5-777d-453d-8849-e345b81fe2cc")


class ScenarioFamily(StrEnum):
    OBSERVATION = "OBSERVATION"
    DATE_BOUNDARY = "DATE_BOUNDARY"
    MATCHING = "MATCHING"
    LIFECYCLE = "LIFECYCLE"
    SOURCE_HEALTH = "SOURCE_HEALTH"
    CLASSIFICATION = "CLASSIFICATION"
    EVIDENCE = "EVIDENCE"
    DATA_QUALITY = "DATA_QUALITY"
    COMMERCIAL = "COMMERCIAL"
    PAIRWISE = "PAIRWISE"


@dataclass(frozen=True)
class Scenario:
    key: str
    family: ScenarioFamily
    description: str
    overrides: Mapping[str, FeatureValue]
    invariants: frozenset[str] = frozenset()

    def snapshot(self, *, as_of_date: date) -> FeatureSnapshot:
        features = baseline_features(as_of_date)
        unknown = set(self.overrides) - set(features)
        if unknown:
            raise ValueError(f"scenario {self.key} has unknown features: {sorted(unknown)}")
        features.update(self.overrides)
        return materialize_relative_values(
            FeatureSnapshot(
                signal_id=uuid5(SCENARIO_NAMESPACE, self.key),
                as_of_date=as_of_date,
                features=features,
                schema_revision=FEATURE_SCHEMA_REVISION,
            )
        )


def baseline_features(as_of_date: date) -> dict[str, FeatureValue]:
    """One complete, ordinary rental-listing observation used only by the harness."""

    first_seen = datetime.combine(as_of_date - timedelta(days=2), time(8), tzinfo=UTC)
    last_seen = datetime.combine(as_of_date, time(8), tzinfo=UTC)
    return {
        "event_type": present("RENTAL_LISTED"),
        "classification_tags": present(["APARTMENT", "STANDARD_HOUSING"]),
        "first_seen_at": present(first_seen),
        "last_seen_at": present(last_seen),
        "listed_at": unavailable("publisher publication date is not persisted canonically"),
        "available_from": present(as_of_date + timedelta(days=45)),
        "application_deadline": present(as_of_date + timedelta(days=10)),
        "lead_time_days": present("47.000"),
        "signal_age_days": present(2),
        "days_until_available": present(45),
        "listing_status": present("ACTIVE"),
        "signal_status": present("ACTIVE"),
        "consecutive_misses": present(0),
        "outcome_types": present([]),
        "property_match": present("STRONG_MATCH"),
        "unit_identifier_present": present(True),
        "rooms": present("3.0"),
        "area_m2": present("82.00"),
        "property_type": present("APARTMENT"),
        "monthly_rent": present("12400.00"),
        "coordinates_present": present(True),
        "distance_to_service_base_km": unavailable(
            "requires a moving-company service base"
        ),
        "source_id": present(SOURCE_ID),
        "source_item_id": present("scenario-listing-1"),
        "publisher_channel": present("uppsala-bostadsformedling"),
        "housing_provider": present("uppsalahem"),
        "snapshot_status": present("COMPLETE"),
        "source_run_status": present("SUCCESS"),
        "evidence_count": present(1),
        "independent_evidence_count": present(1),
        "contradictory_evidence_present": unavailable(
            "cross-evidence contradiction rules are not implemented"
        ),
        "parser_warnings": unavailable("parser warnings are not persisted structurally"),
    }


def scenario_catalog() -> tuple[Scenario, ...]:
    scenarios = [
        *_event_scenarios(),
        *_date_scenarios(),
        *_freshness_scenarios(),
        *_classification_scenarios(),
        *_targeted_scenarios(),
        *_pairwise_scenarios(),
    ]
    keys = [scenario.key for scenario in scenarios]
    if len(keys) != len(set(keys)):
        raise ValueError("scenario catalog keys must be unique")
    return tuple(scenarios)


def scenario_catalog_fingerprint(*, as_of_date: date) -> str:
    payload = [
        {
            "family": scenario.family.value,
            "invariants": sorted(scenario.invariants),
            "key": scenario.key,
            "snapshot_hash": scenario.snapshot(as_of_date=as_of_date).fingerprint(),
        }
        for scenario in scenario_catalog()
    ]
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode()).hexdigest()


def _event_scenarios() -> Iterable[Scenario]:
    for event_type in FEATURES_BY_NAME["event_type"].allowed_values:
        yield Scenario(
            key=f"event-{event_type.lower().replace('_', '-')}",
            family=ScenarioFamily.OBSERVATION,
            description=f"Normalized observation type is {event_type}.",
            overrides={"event_type": present(event_type)},
            invariants=frozenset({"event_semantics_explicit"}),
        )


def _date_scenarios() -> Iterable[Scenario]:
    for offset in (-180, -1, 0, 1, 7, 14, 30, 60, 90, 180, 730):
        yield Scenario(
            key=f"available-{_signed(offset)}-days",
            family=ScenarioFamily.DATE_BOUNDARY,
            description=f"Available-from is {offset} calendar days from as_of.",
            overrides={
                "available_from": present(_date_marker(offset)),
                "days_until_available": present(offset),
            },
            invariants=frozenset({"deterministic", "timing_boundary"}),
        )
    yield Scenario(
        key="available-date-missing",
        family=ScenarioFamily.DATE_BOUNDARY,
        description="No advertised availability date exists.",
        overrides={
            "available_from": missing("listing has no available date"),
            "days_until_available": missing("available date is missing"),
            "lead_time_days": missing("available date is missing"),
        },
        invariants=frozenset({"missing_cannot_improve", "timing_unknown"}),
    )
    yield Scenario(
        key="available-before-first-seen",
        family=ScenarioFamily.DATE_BOUNDARY,
        description=(
            "Availability precedes first observation and must remain visible as invalid input."
        ),
        overrides={
            "available_from": present(_date_marker(-10)),
            "days_until_available": present(-10),
            "lead_time_days": missing("measurement status is INVALID_INPUT"),
        },
        invariants=frozenset({"invalid_timing_visible"}),
    )


def _freshness_scenarios() -> Iterable[Scenario]:
    for age in (0, 1, 30, 31, 90, 91, 120, 121, 365):
        yield Scenario(
            key=f"signal-age-{age}-days",
            family=ScenarioFamily.LIFECYCLE,
            description=f"Signal age is exactly {age} calendar days.",
            overrides={"signal_age_days": present(age)},
            invariants=frozenset({"freshness_boundary", "staleness_cannot_improve"}),
        )


def _classification_scenarios() -> Iterable[Scenario]:
    for classification in FEATURES_BY_NAME["classification_tags"].allowed_values:
        yield Scenario(
            key=f"classification-{classification.lower().replace('_', '-')}",
            family=ScenarioFamily.CLASSIFICATION,
            description=f"Listing has explicit classification {classification}.",
            overrides={"classification_tags": present([classification])},
            invariants=frozenset({"classification_explicit"}),
        )


def _targeted_scenarios() -> tuple[Scenario, ...]:
    return (
        Scenario(
            "uncertain-property-match",
            ScenarioFamily.MATCHING,
            "Property identity is plausible but ambiguous.",
            {"property_match": present("UNCERTAIN_MATCH")},
            frozenset({"confidence_not_strength", "warning_required"}),
        ),
        Scenario(
            "no-property-match",
            ScenarioFamily.MATCHING,
            "A valid new observation has no existing property identity to reuse.",
            {"property_match": present("NO_MATCH")},
            frozenset(
                {"no_match_is_not_invalid_data", "confidence_not_strength", "warning_required"}
            ),
        ),
        Scenario(
            "new-property-without-unit-identifier",
            ScenarioFamily.MATCHING,
            "A separate property was created; absence of a unit ID stays a distinct limitation.",
            {"property_match": present("NO_MATCH"), "unit_identifier_present": present(False)},
            frozenset(
                {"no_match_is_not_invalid_data", "confidence_not_strength", "warning_required"}
            ),
        ),
        Scenario(
            "property-match-missing",
            ScenarioFamily.MATCHING,
            "No property reuse decision was captured; this is not a known NO_MATCH decision.",
            {"property_match": missing("property reuse decision was not recorded")},
            frozenset({"confidence_not_strength", "warning_required"}),
        ),
        Scenario(
            "property-match-conflicting",
            ScenarioFamily.MATCHING,
            "Linked observations disagree on the property reuse decision.",
            {
                "property_match": FeatureValue(
                    FeatureValueState.CONFLICTING,
                    ["NO_MATCH", "UNCERTAIN_MATCH"],
                    "linked property reuse decisions disagree",
                )
            },
            frozenset({"confidence_not_strength", "warning_required"}),
        ),
        Scenario(
            "unit-identifier-missing",
            ScenarioFamily.MATCHING,
            "Publisher omitted the dwelling unit identifier.",
            {"unit_identifier_present": present(False)},
            frozenset({"confidence_not_strength", "warning_required"}),
        ),
        Scenario(
            "listing-removal-candidate",
            ScenarioFamily.LIFECYCLE,
            "Listing is absent from one eligible complete snapshot.",
            {"listing_status": present("REMOVAL_CANDIDATE"), "consecutive_misses": present(1)},
            frozenset({"listing_signal_state_separate"}),
        ),
        Scenario(
            "listing-removed-signal-active",
            ScenarioFamily.LIFECYCLE,
            "Listing is removed while the inferred signal remains active.",
            {
                "listing_status": present("REMOVED"),
                "signal_status": present("ACTIVE"),
                "consecutive_misses": present(2),
                "outcome_types": present(["LISTING_REMOVED"]),
            },
            frozenset({"listing_signal_state_separate", "removal_is_not_confirmed_move"}),
        ),
        Scenario(
            "stale-active-listing",
            ScenarioFamily.LIFECYCLE,
            "Listing remains active but evidence is old.",
            {"signal_age_days": present(150)},
            frozenset({"staleness_cannot_improve"}),
        ),
        Scenario(
            "available-date-moved-forward",
            ScenarioFamily.LIFECYCLE,
            "An observed availability date changed to a later date.",
            {
                "available_from": present(_date_marker(90)),
                "days_until_available": present(90),
                "outcome_types": present(["AVAILABLE_DATE_CHANGED"]),
            },
            frozenset({"date_change_explained", "timing_changed"}),
        ),
        Scenario(
            "available-date-moved-backward",
            ScenarioFamily.LIFECYCLE,
            "An observed availability date changed to an earlier date.",
            {
                "available_from": present(_date_marker(7)),
                "days_until_available": present(7),
                "outcome_types": present(["AVAILABLE_DATE_CHANGED"]),
            },
            frozenset({"date_change_explained", "timing_changed"}),
        ),
        Scenario(
            "listing-relisted",
            ScenarioFamily.LIFECYCLE,
            "A previously removed listing was observed again.",
            {"listing_status": present("ACTIVE"), "outcome_types": present(["LISTING_RELISTED"])},
            frozenset({"relisting_visible", "listing_signal_state_separate"}),
        ),
        Scenario(
            "incomplete-successful-run",
            ScenarioFamily.SOURCE_HEALTH,
            "Collection succeeded technically but did not prove a complete inventory.",
            {"snapshot_status": present("INCOMPLETE"), "source_run_status": present("SUCCESS")},
            frozenset({"no_safe_removal", "confidence_not_strength"}),
        ),
        Scenario(
            "failed-unknown-run",
            ScenarioFamily.SOURCE_HEALTH,
            "Collection failed and completeness is unknown.",
            {"snapshot_status": present("UNKNOWN"), "source_run_status": present("FAILED")},
            frozenset({"no_safe_removal", "warning_required"}),
        ),
        Scenario(
            "special-housing-multi-label",
            ScenarioFamily.CLASSIFICATION,
            "A student dwelling is also short-term and must retain both labels.",
            {"classification_tags": present(["APARTMENT", "SHORT_TERM", "STUDENT_HOUSING"])},
            frozenset({"multi_label_preserved"}),
        ),
        Scenario(
            "duplicate-observations-one-provenance",
            ScenarioFamily.EVIDENCE,
            "Three evidence rows originate from one publisher/provider pair.",
            {"evidence_count": present(3), "independent_evidence_count": present(1)},
            frozenset({"duplicates_not_independent"}),
        ),
        Scenario(
            "independent-corroboration",
            ScenarioFamily.EVIDENCE,
            "Two independently proven publisher/provider observations agree.",
            {"evidence_count": present(2), "independent_evidence_count": present(2)},
            frozenset({"independence_may_strengthen"}),
        ),
        Scenario(
            "conflicting-availability",
            ScenarioFamily.EVIDENCE,
            "Linked evidence disagrees on a material availability date.",
            {
                "available_from": FeatureValue(
                    FeatureValueState.CONFLICTING,
                    [_date_marker(30), _date_marker(60)],
                    "linked evidence contains different material values",
                ),
                "days_until_available": FeatureValue(
                    FeatureValueState.CONFLICTING,
                    [30, 60],
                    "linked evidence contains different material values",
                ),
            },
            frozenset({"conflict_visible", "eligibility_guard"}),
        ),
        Scenario(
            "coordinates-missing",
            ScenarioFamily.DATA_QUALITY,
            "Address has no usable coordinates.",
            {"coordinates_present": present(False)},
            frozenset({"spatial_filter_disabled", "strength_unchanged"}),
        ),
        Scenario(
            "application-deadline-missing",
            ScenarioFamily.DATA_QUALITY,
            "Publisher supplied no application deadline.",
            {"application_deadline": missing("listing has no application deadline")},
            frozenset({"timing_context_missing", "strength_unchanged"}),
        ),
        Scenario(
            "source-item-identity-missing",
            ScenarioFamily.DATA_QUALITY,
            "No stable source item identity was available.",
            {"source_item_id": missing("source item identity is missing")},
            frozenset({"confidence_not_strength", "warning_required"}),
        ),
        Scenario(
            "commercial-fields-missing",
            ScenarioFamily.COMMERCIAL,
            "Rooms, area and rent are unknown.",
            {
                "rooms": missing("rooms are missing"),
                "area_m2": missing("area is missing"),
                "monthly_rent": missing("rent is missing"),
            },
            frozenset({"commercial_only", "strength_unchanged"}),
        ),
        Scenario(
            "large-expensive-home",
            ScenarioFamily.COMMERCIAL,
            "Commercial context is large and expensive but not stronger move evidence.",
            {
                "rooms": present("6.0"),
                "area_m2": present("180.00"),
                "monthly_rent": present("32000.00"),
            },
            frozenset({"commercial_only", "strength_unchanged"}),
        ),
    )


def _pairwise_scenarios() -> Iterable[Scenario]:
    axes: dict[str, dict[str, Mapping[str, FeatureValue]]] = {
        "timing": {
            "missing": {
                "available_from": missing("listing has no available date"),
                "days_until_available": missing("available date is missing"),
            },
            "near": {
                "available_from": present(_date_marker(14)),
                "days_until_available": present(14),
            },
            "past": {
                "available_from": present(_date_marker(-30)),
                "days_until_available": present(-30),
            },
        },
        "match": {
            "strong": {"property_match": present("STRONG_MATCH")},
            "uncertain": {"property_match": present("UNCERTAIN_MATCH")},
            "none": {"property_match": present("NO_MATCH")},
        },
        "lifecycle": {
            "active": {"listing_status": present("ACTIVE"), "consecutive_misses": present(0)},
            "candidate": {
                "listing_status": present("REMOVAL_CANDIDATE"),
                "consecutive_misses": present(1),
            },
            "removed": {"listing_status": present("REMOVED"), "consecutive_misses": present(2)},
        },
        "source": {
            "complete": {
                "snapshot_status": present("COMPLETE"),
                "source_run_status": present("SUCCESS"),
            },
            "incomplete": {
                "snapshot_status": present("INCOMPLETE"),
                "source_run_status": present("SUCCESS"),
            },
            "failed": {
                "snapshot_status": present("UNKNOWN"),
                "source_run_status": present("FAILED"),
            },
        },
    }
    names = tuple(axes)
    levels = tuple(tuple(axes[name]) for name in names)
    for index, values in enumerate(pairwise_cover(levels), start=1):
        labels = dict(zip(names, values, strict=True))
        overrides: dict[str, FeatureValue] = {}
        for name, value in labels.items():
            overrides.update(axes[name][value])
        yield Scenario(
            key=f"pairwise-{index:02d}-" + "-".join(labels.values()),
            family=ScenarioFamily.PAIRWISE,
            description=", ".join(f"{name}={value}" for name, value in labels.items()),
            overrides=overrides,
            invariants=frozenset({"pairwise", "deterministic"}),
        )


def pairwise_cover(axes: Sequence[Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    """Return a deterministic greedy covering array for all cross-axis value pairs."""

    if len(axes) < 2 or any(not axis for axis in axes):
        raise ValueError("pairwise coverage requires at least two non-empty axes")
    candidates = tuple(product(*axes))
    required = {
        (left, candidate[left], right, candidate[right])
        for candidate in candidates
        for left, right in combinations(range(len(axes)), 2)
    }
    selected: list[tuple[str, ...]] = []
    while required:
        best = max(
            candidates,
            key=lambda candidate: (
                len(_pairs(candidate) & required),
                tuple(reversed(candidate)),
            ),
        )
        covered = _pairs(best) & required
        if not covered:
            raise RuntimeError("pairwise catalog could not cover remaining pairs")
        selected.append(best)
        required -= covered
    return tuple(selected)


def _pairs(candidate: Sequence[str]) -> set[tuple[int, str, int, str]]:
    return {
        (left, candidate[left], right, candidate[right])
        for left, right in combinations(range(len(candidate)), 2)
    }


def _date_marker(offset: int) -> dict[str, int]:
    """Resolve relative dates only when a scenario snapshot receives its explicit as_of."""

    return {"days_from_as_of": offset}


def materialize_relative_values(snapshot: FeatureSnapshot) -> FeatureSnapshot:
    """Turn relative scenario date markers into concrete ISO dates before evaluation."""

    features: dict[str, FeatureValue] = {}
    for name, feature in snapshot.features.items():
        value = feature.value
        if isinstance(value, dict) and set(value) == {"days_from_as_of"}:
            value = snapshot.as_of_date + timedelta(days=int(value["days_from_as_of"]))
        elif isinstance(value, list):
            value = [
                snapshot.as_of_date + timedelta(days=int(item["days_from_as_of"]))
                if isinstance(item, dict) and set(item) == {"days_from_as_of"}
                else item
                for item in value
            ]
        features[name] = FeatureValue(feature.state, value, feature.reason)
    return FeatureSnapshot(
        snapshot.signal_id, snapshot.as_of_date, features, snapshot.schema_revision
    )


def _signed(value: int) -> str:
    return f"plus-{value}" if value >= 0 else f"minus-{abs(value)}"
