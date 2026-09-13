"""Stable feature responsibilities for the signal engine.

This registry describes what a feature may influence. It does not activate a score rule.
"""

from dataclasses import dataclass
from enum import StrEnum


class FeatureDimension(StrEnum):
    SIGNAL_STRENGTH = "SIGNAL_STRENGTH"
    DATA_CONFIDENCE = "DATA_CONFIDENCE"
    TIMING = "TIMING"
    COMMERCIAL_RELEVANCE = "COMMERCIAL_RELEVANCE"


class FeatureUse(StrEnum):
    SCORING = "SCORING"
    FILTERING = "FILTERING"
    EXPLANATION = "EXPLANATION"
    ANALYTICS = "ANALYTICS"
    LIFECYCLE = "LIFECYCLE"
    ELIGIBILITY = "ELIGIBILITY"
    WARNING = "WARNING"


class FeatureAvailability(StrEnum):
    CURRENT = "CURRENT"
    DERIVED = "DERIVED"
    INGESTION_ONLY = "INGESTION_ONLY"
    PLANNED = "PLANNED"


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    definition: str
    source: str
    value_type: str
    missing_semantics: str
    affects: frozenset[FeatureDimension]
    prohibits: frozenset[FeatureDimension]
    uses: frozenset[FeatureUse]
    allowed_values: tuple[str, ...] = ()
    availability: FeatureAvailability = FeatureAvailability.CURRENT


def _spec(
    name: str,
    definition: str,
    source: str,
    value_type: str,
    missing_semantics: str,
    *,
    affects: tuple[FeatureDimension, ...] = (),
    prohibits: tuple[FeatureDimension, ...] = (),
    uses: tuple[FeatureUse, ...] = (),
    allowed_values: tuple[str, ...] = (),
    availability: FeatureAvailability = FeatureAvailability.CURRENT,
) -> FeatureSpec:
    return FeatureSpec(
        name=name,
        definition=definition,
        source=source,
        value_type=value_type,
        missing_semantics=missing_semantics,
        affects=frozenset(affects),
        prohibits=frozenset(prohibits),
        uses=frozenset(uses),
        allowed_values=allowed_values,
        availability=availability,
    )


STRENGTH = FeatureDimension.SIGNAL_STRENGTH
CONFIDENCE = FeatureDimension.DATA_CONFIDENCE
TIMING = FeatureDimension.TIMING
COMMERCIAL = FeatureDimension.COMMERCIAL_RELEVANCE
SCORE = FeatureUse.SCORING
FILTER = FeatureUse.FILTERING
EXPLAIN = FeatureUse.EXPLANATION
ANALYZE = FeatureUse.ANALYTICS
LIFECYCLE = FeatureUse.LIFECYCLE
ELIGIBILITY = FeatureUse.ELIGIBILITY
WARNING = FeatureUse.WARNING


FEATURE_REGISTRY: tuple[FeatureSpec, ...] = (
    _spec(
        "event_type",
        "Domain interpretation of the source observation.",
        "events.event_type",
        "enum",
        "Missing means no scoreable event and blocks signal evaluation.",
        affects=(STRENGTH, TIMING),
        uses=(SCORE, FILTER, EXPLAIN, ELIGIBILITY),
        allowed_values=(
            "RENTAL_LISTED",
            "LISTING_REMOVED",
            "NEW_BUILD_MOVE_IN",
            "SALE_LISTED",
            "SALE_SOLD",
            "LEASE_TERMINATED",
            "PROPERTY_TRANSFERRED",
        ),
    ),
    _spec(
        "classification_tags",
        "Explicit, multi-label housing classifications.",
        "rental_listing_classifications",
        "set[enum]",
        "No recognized category is stored explicitly as UNKNOWN.",
        affects=(STRENGTH, COMMERCIAL),
        uses=(SCORE, FILTER, EXPLAIN, ANALYZE),
        allowed_values=(
            "APARTMENT",
            "HOUSE",
            "NEW_CONSTRUCTION",
            "PERMANENT_CONTRACT",
            "ROOM",
            "SENIOR_HOUSING",
            "SHORT_TERM",
            "STANDARD_HOUSING",
            "STUDENT_HOUSING",
            "UNKNOWN",
            "YOUTH_HOUSING",
        ),
    ),
    _spec(
        "first_seen_at",
        "First time this normalized listing identity was observed.",
        "rental_listings.first_seen_at",
        "datetime",
        "Missing makes lead time unavailable; it is never imputed.",
        affects=(TIMING,),
        uses=(SCORE, EXPLAIN, ANALYZE),
    ),
    _spec(
        "last_seen_at",
        "Most recent successful observation of the listing identity.",
        "rental_listings.last_seen_at",
        "datetime",
        "Missing lowers confidence and blocks freshness calculations.",
        affects=(STRENGTH, CONFIDENCE, TIMING),
        uses=(SCORE, EXPLAIN, ANALYZE, WARNING),
    ),
    _spec(
        "listed_at",
        "Publisher-provided publication date when available.",
        "normalized ingestion item",
        "date",
        "Missing is unknown, not zero age; the canonical listing does not persist it yet.",
        affects=(STRENGTH, TIMING),
        uses=(SCORE, EXPLAIN, ANALYZE),
        availability=FeatureAvailability.INGESTION_ONLY,
    ),
    _spec(
        "available_from",
        "Advertised date from which the dwelling is available.",
        "rental_listings.available_from",
        "date",
        "Missing produces unknown timing and cannot receive known-date strength.",
        affects=(STRENGTH, TIMING),
        uses=(SCORE, FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "application_deadline",
        "Advertised final application date.",
        "rental_listings.application_deadline",
        "date",
        "Missing is reported as unavailable and is not inferred.",
        affects=(TIMING,),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "lead_time_days",
        "Available-from date minus first-seen date in Europe/Stockholm.",
        "listing_measurements: LEAD_TIME_DAYS",
        "decimal days",
        "MISSING_INPUT and INVALID_INPUT remain explicit measurement states.",
        affects=(TIMING,),
        uses=(SCORE, FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "signal_age_days",
        "Calendar age of the signal at an explicit as_of date.",
        "derived from signals.created_at",
        "integer days",
        "Requires as_of and created_at; evaluation fails closed if either is absent.",
        affects=(CONFIDENCE, TIMING),
        uses=(SCORE, FILTER, EXPLAIN, ANALYZE),
        availability=FeatureAvailability.DERIVED,
    ),
    _spec(
        "days_until_available",
        "Calendar distance from as_of to available_from.",
        "derived from available_from",
        "integer days",
        "Missing available_from yields unknown timing, never a sentinel number.",
        affects=(STRENGTH, TIMING),
        uses=(SCORE, FILTER, EXPLAIN, ANALYZE),
        availability=FeatureAvailability.DERIVED,
    ),
    _spec(
        "listing_status",
        "Lifecycle state of the source listing, separate from signal status.",
        "rental_listings.status",
        "enum",
        "Missing status blocks eligibility; it is not treated as ACTIVE.",
        affects=(STRENGTH, CONFIDENCE, TIMING),
        uses=(SCORE, FILTER, EXPLAIN, LIFECYCLE, ELIGIBILITY, WARNING),
        allowed_values=("ACTIVE", "REMOVAL_CANDIDATE", "REMOVED"),
    ),
    _spec(
        "signal_status",
        "Lifecycle state of the inference, independent of listing status.",
        "signals.status",
        "enum",
        "Missing blocks product eligibility.",
        affects=(TIMING,),
        uses=(FILTER, EXPLAIN, LIFECYCLE, ELIGIBILITY),
        allowed_values=("ACTIVE",),
    ),
    _spec(
        "consecutive_misses",
        "Eligible complete snapshots in which a listing was absent.",
        "rental_listings.consecutive_misses",
        "integer",
        "Unknown is not equivalent to zero and cannot trigger removal.",
        affects=(CONFIDENCE, TIMING),
        uses=(EXPLAIN, LIFECYCLE, ELIGIBILITY, WARNING),
    ),
    _spec(
        "outcome_types",
        "Observed later facts linked to the signal; not all outcomes confirm a move.",
        "signal_outcomes.outcome_type",
        "set[enum]",
        "An empty set means no observed outcome, not a negative outcome.",
        affects=(STRENGTH, TIMING),
        uses=(SCORE, FILTER, EXPLAIN, ANALYZE),
        allowed_values=(
            "AVAILABLE_DATE_CHANGED",
            "CONFIRMED_MOVE",
            "CROSS_SOURCE_CONFIRMED",
            "LISTING_RELISTED",
            "LISTING_REMOVED",
            "UNKNOWN",
        ),
    ),
    _spec(
        "property_match",
        "Property reuse decision; NO_MATCH means no reusable identity, not invalid source data.",
        "events.metadata.property_match",
        "enum",
        "Missing/conflicting/uncertain reuse lowers confidence; NO_MATCH is neutral and visible.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(SCORE, FILTER, EXPLAIN, ELIGIBILITY, WARNING, ANALYZE),
        allowed_values=("NO_MATCH", "STRONG_MATCH", "UNCERTAIN_MATCH"),
    ),
    _spec(
        "unit_identifier_present",
        "Whether the source supplied a dwelling/unit identifier.",
        "rental_listings.unit_identifier",
        "boolean",
        "False is explicit missing identity and may lower match confidence.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(EXPLAIN, ELIGIBILITY, WARNING, ANALYZE),
        availability=FeatureAvailability.DERIVED,
    ),
    _spec(
        "rooms",
        "Advertised room count for the listing.",
        "rental_listings.rooms",
        "decimal",
        "Missing stays unknown and is not replaced with a default.",
        affects=(COMMERCIAL,),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "area_m2",
        "Advertised dwelling area in square metres.",
        "rental_listings.area_m2",
        "decimal",
        "Missing stays unknown and is not replaced with zero.",
        affects=(COMMERCIAL,),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "property_type",
        "Normalized dwelling type.",
        "properties.property_type",
        "string",
        "Missing remains UNKNOWN and cannot be guessed from area or rooms.",
        affects=(COMMERCIAL,),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "monthly_rent",
        "Advertised monthly rent.",
        "rental_listings.monthly_rent",
        "decimal SEK",
        "Missing stays unknown; it is not imputed from area or provider.",
        affects=(COMMERCIAL,),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "coordinates_present",
        "Whether the normalized address has usable map coordinates.",
        "addresses.geometry",
        "boolean",
        "False disables spatial operations and creates an explicit warning.",
        affects=(CONFIDENCE, COMMERCIAL),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ELIGIBILITY, WARNING, ANALYZE),
        availability=FeatureAvailability.DERIVED,
    ),
    _spec(
        "distance_to_service_base_km",
        "Metric distance from a company-configured service base.",
        "derived from coordinates and company profile",
        "decimal kilometres",
        "Unknown until both coordinates and a company profile exist.",
        affects=(COMMERCIAL,),
        prohibits=(STRENGTH, CONFIDENCE),
        uses=(FILTER, EXPLAIN, ANALYZE),
        availability=FeatureAvailability.PLANNED,
    ),
    _spec(
        "source_id",
        "Identity of the configured collection channel.",
        "events.source_id",
        "uuid",
        "Missing breaks provenance and blocks evaluation.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(FILTER, EXPLAIN, ANALYZE, ELIGIBILITY),
    ),
    _spec(
        "source_item_id",
        "Stable item identity within one source when provided.",
        "rental_listings.source_item_id",
        "string",
        "Missing or unstable identity lowers confidence and cannot be synthesized silently.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(EXPLAIN, ELIGIBILITY, WARNING, ANALYZE),
    ),
    _spec(
        "publisher_channel",
        "Channel through which the observation was collected.",
        "source provenance",
        "identifier",
        "Missing channel identity blocks claims of independent evidence.",
        affects=(CONFIDENCE,),
        prohibits=(COMMERCIAL,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "housing_provider",
        "Landlord or housing organization behind the listing.",
        "rental_listings.upstream_provider_key",
        "identifier",
        "Missing remains an unknown provider; publisher is not substituted.",
        affects=(COMMERCIAL,),
        prohibits=(STRENGTH,),
        uses=(FILTER, EXPLAIN, ANALYZE),
    ),
    _spec(
        "snapshot_status",
        "Completeness assessment of the collection run.",
        "source_runs.snapshot_status",
        "enum",
        "UNKNOWN is explicit and cannot authorize absence-based lifecycle writes.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(EXPLAIN, LIFECYCLE, ELIGIBILITY, WARNING, ANALYZE),
        allowed_values=("COMPLETE", "INCOMPLETE", "UNKNOWN"),
    ),
    _spec(
        "source_run_status",
        "Execution result of the collection run.",
        "source_runs.status",
        "enum",
        "Missing or non-successful runs cannot support lifecycle conclusions.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(EXPLAIN, LIFECYCLE, ELIGIBILITY, WARNING, ANALYZE),
        allowed_values=("FAILED", "RUNNING", "SUCCESS"),
    ),
    _spec(
        "evidence_count",
        "Number of evidence rows, including observations that may not be independent.",
        "signal_evidence",
        "integer",
        "Zero blocks evaluation; count alone must not increase strength.",
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(EXPLAIN, ANALYZE, WARNING),
        availability=FeatureAvailability.DERIVED,
    ),
    _spec(
        "independent_evidence_count",
        "Deduplicated evidence count after publisher and provider provenance checks.",
        "derived from signal evidence provenance",
        "integer",
        "Unknown independence is treated as one uncorroborated observation, not many.",
        affects=(STRENGTH, CONFIDENCE),
        uses=(SCORE, EXPLAIN, ANALYZE),
        availability=FeatureAvailability.DERIVED,
    ),
    _spec(
        "contradictory_evidence_present",
        "Whether independent observations disagree on material identity or timing facts.",
        "derived from evidence comparison",
        "boolean",
        "Unknown comparison state cannot be treated as agreement.",
        affects=(STRENGTH, CONFIDENCE),
        uses=(SCORE, EXPLAIN, ELIGIBILITY, WARNING, ANALYZE),
        availability=FeatureAvailability.PLANNED,
    ),
    _spec(
        "parser_warnings",
        "Structured warnings emitted while parsing or normalizing source data.",
        "source adapter and normalization",
        "set[code]",
        "No stored warning information is unknown, not proof of clean parsing.",
        affects=(CONFIDENCE,),
        prohibits=(STRENGTH, COMMERCIAL),
        uses=(EXPLAIN, ELIGIBILITY, WARNING, ANALYZE),
        availability=FeatureAvailability.PLANNED,
    ),
)


FEATURES_BY_NAME = {feature.name: feature for feature in FEATURE_REGISTRY}
