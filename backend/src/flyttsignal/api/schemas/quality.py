from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class QualityRatioOut(BaseModel):
    numerator: int
    denominator: int
    percent: Decimal | None


class QualityStrengthBucketOut(BaseModel):
    label: str
    min_strength: int
    max_strength: int
    count: int


class QualitySourceOut(BaseModel):
    source_key: str
    source_name: str
    active_listing_count: int
    unique_property_count: int
    missing_available_from_count: int
    latest_run_at: datetime | None
    latest_execution_status: str | None
    latest_snapshot_status: str | None
    completeness_rule_version: str | None


class QualityFindingOut(BaseModel):
    severity: str
    code: str
    message: str


class QualitySummaryOut(BaseModel):
    generated_at: datetime
    rule_version: str
    city_id: int
    city: str
    data_mode: str
    listing_population_count: int
    unique_property_count: int
    signal_population_count: int
    active_signal_count: int
    closed_signal_count: int
    strong_signal_count: int
    average_evidence_count: Decimal | None
    median_signal_age_days: Decimal | None
    median_lead_time_days: Decimal | None
    classification_coverage: QualityRatioOut
    unknown_classification_rate: QualityRatioOut
    measurement_record_coverage: QualityRatioOut
    usable_lead_time_rate: QualityRatioOut
    missing_available_from_rate: QualityRatioOut
    same_source_duplicate_rate: QualityRatioOut
    cross_source_property_overlap_rate: QualityRatioOut
    ambiguous_match_rate: QualityRatioOut
    outcome_coverage: QualityRatioOut
    outcome_count: int
    confirmed_move_count: int
    signal_strength_distribution: list[QualityStrengthBucketOut]
    sources: list[QualitySourceOut]
    findings: list[QualityFindingOut]
