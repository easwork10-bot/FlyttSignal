from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from flyttsignal.api.schemas.quality import (
    QualityFindingOut,
    QualityRatioOut,
    QualitySourceOut,
    QualityStrengthBucketOut,
    QualitySummaryOut,
)
from flyttsignal.db.repositories.quality import QualityDataset

QUALITY_RULE_VERSION = "quality-v2"
STRONG_SIGNAL_THRESHOLD = 60


def _decimal(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ratio(numerator: int, denominator: int) -> QualityRatioOut:
    percent = None if denominator == 0 else _decimal(numerator * 100 / denominator)
    return QualityRatioOut(numerator=numerator, denominator=denominator, percent=percent)


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    value = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / Decimal(2)
    )
    return _decimal(value)


def build_quality_summary(
    dataset: QualityDataset, *, generated_at: datetime | None = None
) -> QualitySummaryOut:
    now = generated_at or datetime.now(UTC)
    listing_count = len(dataset.listings)
    property_sources: dict[object, set[object]] = defaultdict(set)
    source_properties: dict[object, set[object]] = defaultdict(set)
    source_listings: dict[object, list] = defaultdict(list)
    source_property_counts: dict[tuple[object, object], int] = defaultdict(int)
    for listing in dataset.listings:
        property_sources[listing.property_id].add(listing.source_id)
        source_properties[listing.source_id].add(listing.property_id)
        source_listings[listing.source_id].append(listing)
        source_property_counts[(listing.source_id, listing.property_id)] += 1

    unique_property_count = len(property_sources)
    duplicate_excess = sum(max(count - 1, 0) for count in source_property_counts.values())
    overlap_properties = sum(len(source_ids) > 1 for source_ids in property_sources.values())
    missing_dates = sum(not item.available_from_present for item in dataset.listings)

    signal_count = len(dataset.signals)
    active_signals = sum(item.status == "ACTIVE" for item in dataset.signals)
    evidence_count = sum(item.evidence_count for item in dataset.signals)
    ambiguous_matches = sum(item.ambiguous_match_count for item in dataset.signals)
    signal_ages = [
        Decimal(str(max((now - item.created_at).total_seconds(), 0) / 86400))
        for item in dataset.signals
    ]
    signals_with_outcomes = {item.signal_id for item in dataset.outcomes}

    buckets = (
        ("LOW", 0, 39),
        ("MEDIUM", 40, 59),
        ("STRONG", 60, 79),
        ("VERY_STRONG", 80, 100),
    )
    signal_strength_distribution = [
        QualityStrengthBucketOut(
            label=label,
            min_strength=minimum,
            max_strength=maximum,
            count=sum(
                minimum <= signal.signal_strength <= maximum for signal in dataset.signals
            ),
        )
        for label, minimum, maximum in buckets
    ]

    sources = []
    for source_id, listings in sorted(
        source_listings.items(), key=lambda item: item[1][0].source_key
    ):
        first = listings[0]
        latest = dataset.latest_runs.get(source_id)
        sources.append(
            QualitySourceOut(
                source_key=first.source_key,
                source_name=first.source_name,
                active_listing_count=len(listings),
                unique_property_count=len(source_properties[source_id]),
                missing_available_from_count=sum(
                    not listing.available_from_present for listing in listings
                ),
                latest_run_at=latest.started_at if latest else None,
                latest_execution_status=latest.status.value if latest else None,
                latest_snapshot_status=latest.snapshot_status if latest else None,
                completeness_rule_version=(latest.completeness_rule_version if latest else None),
            )
        )

    findings: list[QualityFindingOut] = []
    if len(dataset.classified_listing_ids) < listing_count:
        findings.append(
            QualityFindingOut(
                severity="WARNING",
                code="CLASSIFICATION_COVERAGE_GAP",
                message="Some active live listings lack classification-v1 rows.",
            )
        )
    if len(dataset.measured_listing_ids) < listing_count:
        findings.append(
            QualityFindingOut(
                severity="WARNING",
                code="MEASUREMENT_COVERAGE_GAP",
                message="Some active live listings lack lead-time-v1 rows.",
            )
        )
    if missing_dates:
        findings.append(
            QualityFindingOut(
                severity="INFO",
                code="MISSING_AVAILABLE_FROM",
                message="Some listings cannot produce usable lead time without available_from.",
            )
        )
    if duplicate_excess:
        findings.append(
            QualityFindingOut(
                severity="WARNING",
                code="SAME_SOURCE_DUPLICATES",
                message="A source contains multiple active listings mapped to the same property.",
            )
        )
    if ambiguous_matches:
        findings.append(
            QualityFindingOut(
                severity="WARNING",
                code="AMBIGUOUS_PROPERTY_MATCHES",
                message="Live signal evidence contains uncertain property matches.",
            )
        )
    for source in sources:
        if source.latest_snapshot_status != "COMPLETE":
            findings.append(
                QualityFindingOut(
                    severity="INFO",
                    code="LATEST_SNAPSHOT_NOT_COMPLETE",
                    message=(
                        f"{source.source_key} latest snapshot is "
                        f"{source.latest_snapshot_status or 'UNKNOWN'}."
                    ),
                )
            )
    if not dataset.outcomes:
        findings.append(
            QualityFindingOut(
                severity="INFO",
                code="NO_OBSERVED_OUTCOMES",
                message="No outcome-v1 facts are currently proven for the live signal population.",
            )
        )

    return QualitySummaryOut(
        generated_at=now,
        rule_version=QUALITY_RULE_VERSION,
        city_id=dataset.city_id,
        city=dataset.city_name,
        data_mode="live",
        listing_population_count=listing_count,
        unique_property_count=unique_property_count,
        signal_population_count=signal_count,
        active_signal_count=active_signals,
        closed_signal_count=signal_count - active_signals,
        strong_signal_count=sum(
            item.signal_strength >= STRONG_SIGNAL_THRESHOLD for item in dataset.signals
        ),
        average_evidence_count=(
            None if signal_count == 0 else _decimal(evidence_count / signal_count)
        ),
        median_signal_age_days=_median(signal_ages),
        median_lead_time_days=_median(list(dataset.usable_lead_time_values)),
        classification_coverage=_ratio(len(dataset.classified_listing_ids), listing_count),
        unknown_classification_rate=_ratio(len(dataset.unknown_listing_ids), listing_count),
        measurement_record_coverage=_ratio(len(dataset.measured_listing_ids), listing_count),
        usable_lead_time_rate=_ratio(len(dataset.usable_lead_time_values), listing_count),
        missing_available_from_rate=_ratio(missing_dates, listing_count),
        same_source_duplicate_rate=_ratio(duplicate_excess, listing_count),
        cross_source_property_overlap_rate=_ratio(overlap_properties, unique_property_count),
        ambiguous_match_rate=_ratio(ambiguous_matches, evidence_count),
        outcome_coverage=_ratio(len(signals_with_outcomes), signal_count),
        outcome_count=len(dataset.outcomes),
        confirmed_move_count=sum(
            item.outcome_type == "CONFIRMED_MOVE"
            and item.subject == "HOUSEHOLD_MOVE"
            and item.verification_level == "CONFIRMED"
            for item in dataset.outcomes
        ),
        signal_strength_distribution=signal_strength_distribution,
        sources=sources,
        findings=findings,
    )
