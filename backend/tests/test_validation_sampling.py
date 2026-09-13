import uuid
from datetime import date

import pytest

from flyttsignal.domains.signals.validation import (
    ValidationCandidate,
    select_validation_sample,
    strength_stratum,
    validate_review,
)


def candidate(score: int, index: int) -> ValidationCandidate:
    tags = ("STUDENT_HOUSING",) if index % 7 == 0 else ("STANDARD_HOUSING",)
    return ValidationCandidate(
        signal_id=uuid.UUID(int=index + 1),
        score_run_id=uuid.UUID(int=999),
        score_as_of_date=date(2026, 9, 8),
        definition_set_hash="a" * 64,
        signal_strength=score,
        data_confidence=55,
        timing=45,
        listing_ids=(uuid.uuid4(),),
        property_ids=(uuid.uuid4(),),
        source_keys=(f"source-{index % 4}",),
        provider_keys=(f"provider-{index % 11}",),
        classification_tags=tags,
        missing_available_from=index % 19 == 0,
        cross_source_property=index % 23 == 0,
    )


def test_sample_is_reproducible_and_reports_low_score_shortage() -> None:
    candidates = [candidate(30, index) for index in range(3)]
    candidates += [candidate(50, index + 3) for index in range(40)]
    candidates += [candidate(70, index + 43) for index in range(40)]

    first = select_validation_sample(candidates, target_size=60, seed="stable")
    second = select_validation_sample(candidates, target_size=60, seed="stable")

    assert [item.candidate.signal_id for item in first.selected] == [
        item.candidate.signal_id for item in second.selected
    ]
    assert first.manifest["population_strata"] == {
        "HIGH": 40,
        "LOW": 3,
        "MEDIUM": 40,
    }
    assert first.manifest["selected_strata"] == {
        "HIGH": 29,
        "LOW": 3,
        "MEDIUM": 28,
    }
    assert len(first.selected) == 60


def test_strength_strata_use_existing_strong_threshold() -> None:
    assert strength_stratum(39) == "LOW"
    assert strength_stratum(40) == "MEDIUM"
    assert strength_stratum(59) == "MEDIUM"
    assert strength_stratum(60) == "HIGH"


def test_review_rules_require_specific_evidence_for_non_good_verdicts() -> None:
    assert validate_review("good", []) == ("GOOD", ())
    assert validate_review("bad", ["bad_match", "bad_match"]) == (
        "BAD",
        ("BAD_MATCH",),
    )
    assert validate_review("questionable", ["stale_normalized_property"]) == (
        "QUESTIONABLE",
        ("STALE_NORMALIZED_PROPERTY",),
    )
    with pytest.raises(ValueError, match="require at least one"):
        validate_review("QUESTIONABLE", [])
    with pytest.raises(ValueError, match="GOOD reviews cannot"):
        validate_review("GOOD", ["OTHER"])
    with pytest.raises(ValueError, match="invalid issue"):
        validate_review("BAD", ["MADE_UP"])
