import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from flyttsignal.db.repositories.quality import (
    ListingQualityFact,
    OutcomeQualityFact,
    QualityDataset,
    SignalQualityFact,
)
from flyttsignal.quality.service import build_quality_summary


def test_quality_summary_keeps_all_rates_auditable() -> None:
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()
    property_id = uuid.uuid4()
    listings = (
        ListingQualityFact(uuid.uuid4(), source_a, "source-a", "Source A", property_id, True),
        ListingQualityFact(uuid.uuid4(), source_a, "source-a", "Source A", property_id, False),
        ListingQualityFact(uuid.uuid4(), source_b, "source-b", "Source B", property_id, True),
    )
    signal_a = uuid.uuid4()
    signal_b = uuid.uuid4()
    signals = (
        SignalQualityFact(signal_a, "ACTIVE", 30, now - timedelta(days=2), 1, 0),
        SignalQualityFact(signal_b, "RESOLVED", 70, now - timedelta(days=4), 2, 1),
    )
    dataset = QualityDataset(
        city_id=1,
        city_name="Uppsala",
        listings=listings,
        classified_listing_ids=frozenset({listings[0].listing_id, listings[1].listing_id}),
        unknown_listing_ids=frozenset({listings[1].listing_id}),
        measured_listing_ids=frozenset(item.listing_id for item in listings),
        usable_lead_time_values=(Decimal("10"), Decimal("20")),
        signals=signals,
        outcomes=(OutcomeQualityFact(signal_b, "LISTING_REMOVED", "LISTING", "OBSERVED"),),
        latest_runs={},
    )

    summary = build_quality_summary(dataset, generated_at=now)

    assert summary.listing_population_count == 3
    assert summary.unique_property_count == 1
    assert summary.signal_population_count == 2
    assert summary.active_signal_count == 1
    assert summary.closed_signal_count == 1
    assert summary.strong_signal_count == 1
    assert summary.rule_version == "quality-v2"
    assert [bucket.model_dump() for bucket in summary.signal_strength_distribution] == [
        {"label": "LOW", "min_strength": 0, "max_strength": 39, "count": 1},
        {"label": "MEDIUM", "min_strength": 40, "max_strength": 59, "count": 0},
        {"label": "STRONG", "min_strength": 60, "max_strength": 79, "count": 1},
        {"label": "VERY_STRONG", "min_strength": 80, "max_strength": 100, "count": 0},
    ]
    assert summary.average_evidence_count == Decimal("1.50")
    assert summary.median_signal_age_days == Decimal("3.00")
    assert summary.median_lead_time_days == Decimal("15.00")
    assert summary.classification_coverage.model_dump() == {
        "numerator": 2,
        "denominator": 3,
        "percent": Decimal("66.67"),
    }
    assert summary.same_source_duplicate_rate.numerator == 1
    assert summary.cross_source_property_overlap_rate.model_dump() == {
        "numerator": 1,
        "denominator": 1,
        "percent": Decimal("100.00"),
    }
    assert summary.ambiguous_match_rate.model_dump() == {
        "numerator": 1,
        "denominator": 3,
        "percent": Decimal("33.33"),
    }
    assert summary.outcome_coverage.numerator == 1
    assert summary.confirmed_move_count == 0


def test_empty_quality_population_uses_null_percentages() -> None:
    summary = build_quality_summary(
        QualityDataset(
            city_id=1,
            city_name="Uppsala",
            listings=(),
            classified_listing_ids=frozenset(),
            unknown_listing_ids=frozenset(),
            measured_listing_ids=frozenset(),
            usable_lead_time_values=(),
            signals=(),
            outcomes=(),
            latest_runs={},
        )
    )

    assert summary.classification_coverage.percent is None
    assert summary.average_evidence_count is None
    assert summary.median_signal_age_days is None
    assert summary.outcome_coverage.percent is None
