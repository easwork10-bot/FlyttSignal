import uuid
from datetime import date
from pathlib import Path

from flyttsignal.api.schemas.signals import EvidenceOut, SignalOut
from flyttsignal.db.models import (
    AddressEnrichment,
    AddressRegisterUnitLink,
    BenchmarkObservation,
    Event,
    HousingProviderCity,
    PilotSignalActivity,
    PilotSignalFeedback,
    ProviderChannel,
    RawItem,
    RentalListing,
    RentalProject,
    Signal,
    SignalEvidence,
    SignalValidation,
    SourceCity,
    SpatialFeature,
    ValidationBatch,
)
from flyttsignal.db.repositories.dashboard import DashboardRepository
from flyttsignal.domains.events.models import EventType
from flyttsignal.domains.signals.models import SignalType
from flyttsignal.domains.signals.pilot import PilotCohortPolicy, PilotSignalFilters
from flyttsignal.ingestion.contracts import (
    AddressEnrichmentAdapter,
    BenchmarkAdapter,
    RentalDevelopmentAdapter,
    SourceAdapter,
    SpatialFeatureAdapter,
)
from flyttsignal.integrations.sources.address_enrichment.lantmateriet import (
    LantmaterietAddressAdapter,
)
from flyttsignal.integrations.sources.benchmark_statistics.scb import SCBMigrationAdapter
from flyttsignal.integrations.sources.rental_developments.homeq import (
    HomeQPublicUppsalaProjectAdapter,
)
from flyttsignal.integrations.sources.rental_listings.heimstaden import HeimstadenUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.homeq import HomeQPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.hsb import HSBPublicUppsalaAdapter
from flyttsignal.integrations.sources.rental_listings.uppsala_bostadsformedling import (
    UppsalaBostadsformedlingAdapter,
)
from flyttsignal.integrations.sources.spatial_features.uppsala_open_data import (
    UppsalaBuildingsAdapter,
)


def foreign_key_targets(model, column_name: str) -> set[str]:
    column = model.__table__.columns[column_name]
    return {foreign_key.target_fullname for foreign_key in column.foreign_keys}


def test_event_orm_column_uses_domain_owned_enum() -> None:
    assert Event.__table__.c.event_type.type.enum_class is EventType


def test_signal_orm_column_uses_domain_owned_enum() -> None:
    assert Signal.__table__.c.signal_type.type.enum_class is SignalType


def test_legacy_flyttscore_is_historical_not_runtime() -> None:
    package_root = Path(__file__).resolve().parents[1] / "src" / "flyttsignal"
    pipeline = (package_root / "ingestion/pipelines/rental_listings.py").read_text(encoding="utf-8")

    assert Signal.__table__.c.score.nullable
    assert "score" not in SignalOut.model_fields
    assert "score_components" not in SignalOut.model_fields
    assert not (package_root / "domains/signals/scoring.py").exists()
    assert "calculate_score" not in pipeline
    assert "ScoreComponent" not in pipeline
    assert "signal.score" not in pipeline


def test_source_adapters_share_the_generic_contract() -> None:
    adapters = (
        UppsalaBostadsformedlingAdapter,
        HeimstadenUppsalaAdapter,
        HomeQPublicUppsalaAdapter,
        HSBPublicUppsalaAdapter,
    )
    assert all(issubclass(adapter, SourceAdapter) for adapter in adapters)
    assert len({adapter.source_key for adapter in adapters}) == len(adapters)


def test_benchmark_adapter_is_separate_from_property_sources() -> None:
    assert issubclass(SCBMigrationAdapter, BenchmarkAdapter)
    assert not issubclass(SCBMigrationAdapter, SourceAdapter)
    assert foreign_key_targets(BenchmarkObservation, "raw_item_id") == {"raw_items.id"}
    assert "property_id" not in BenchmarkObservation.__table__.columns


def test_address_enrichment_is_separate_from_events_and_signals() -> None:
    assert issubclass(LantmaterietAddressAdapter, AddressEnrichmentAdapter)
    assert not issubclass(LantmaterietAddressAdapter, SourceAdapter)
    assert foreign_key_targets(AddressEnrichment, "raw_item_id") == {"raw_items.id"}
    assert foreign_key_targets(AddressEnrichment, "address_id") == {"addresses.id"}
    assert "property_id" not in AddressEnrichment.__table__.columns
    assert "event_id" not in AddressEnrichment.__table__.columns
    assert foreign_key_targets(AddressRegisterUnitLink, "address_enrichment_id") == {
        "address_enrichments.id"
    }
    assert "property_id" not in AddressRegisterUnitLink.__table__.columns
    assert "event_id" not in AddressRegisterUnitLink.__table__.columns


def test_spatial_features_are_separate_from_property_signals() -> None:
    assert issubclass(UppsalaBuildingsAdapter, SpatialFeatureAdapter)
    assert not issubclass(UppsalaBuildingsAdapter, SourceAdapter)
    assert foreign_key_targets(SpatialFeature, "raw_item_id") == {"raw_items.id"}
    assert "property_id" not in SpatialFeature.__table__.columns
    assert "event_id" not in SpatialFeature.__table__.columns
    assert "signal_id" not in SpatialFeature.__table__.columns


def test_observation_inference_and_raw_evidence_are_relationally_separate() -> None:
    assert foreign_key_targets(Event, "raw_item_id") == {"raw_items.id"}
    assert foreign_key_targets(SignalEvidence, "event_id") == {"events.id"}
    assert foreign_key_targets(SignalEvidence, "signal_id") == {"signals.id"}
    assert RawItem.__table__.columns.raw_payload.nullable is False


def test_signal_evidence_readers_respect_current_and_as_of_semantics() -> None:
    package_root = Path(__file__).resolve().parents[1] / "src" / "flyttsignal"
    current_state_readers = (
        "db/repositories/quality.py",
        "db/repositories/dashboard.py",
        "outcomes/service.py",
        "ingestion/pipelines/rental_listings.py",
        "property_provenance/service.py",
    )

    for relative_path in current_state_readers:
        source = (package_root / relative_path).read_text(encoding="utf-8")
        assert "SignalEvidence.superseded_at.is_(None)" in source, relative_path

    for relative_path in (
        "db/repositories/validation.py",
        "db/repositories/feature_snapshots.py",
    ):
        source = (package_root / relative_path).read_text(encoding="utf-8")
        assert "SignalEvidence.valid_from <=" in source, relative_path
        assert "SignalEvidence.superseded_at >" in source, relative_path


def test_sources_and_cities_have_a_many_to_many_contract() -> None:
    assert foreign_key_targets(SourceCity, "source_id") == {"sources.id"}
    assert foreign_key_targets(SourceCity, "city_id") == {"cities.id"}
    assert {column.name for column in SourceCity.__table__.primary_key.columns} == {
        "source_id",
        "city_id",
    }


def test_signal_evidence_exposes_safe_raw_trace_identifiers() -> None:
    assert {"event_id", "raw_item_id", "source_item_id"} <= EvidenceOut.model_fields.keys()


def test_rental_listing_keeps_publisher_provider_and_property_separate() -> None:
    assert foreign_key_targets(RentalListing, "source_id") == {"sources.id"}
    assert foreign_key_targets(RentalListing, "raw_item_id") == {"raw_items.id"}
    assert foreign_key_targets(RentalListing, "property_id") == {"properties.id"}
    assert "upstream_provider_key" in RentalListing.__table__.columns


def test_provider_coverage_is_relational_and_channels_may_link_collectors() -> None:
    assert foreign_key_targets(HousingProviderCity, "provider_id") == {"housing_providers.id"}
    assert foreign_key_targets(HousingProviderCity, "city_id") == {"cities.id"}
    assert foreign_key_targets(ProviderChannel, "provider_id") == {"housing_providers.id"}
    assert foreign_key_targets(ProviderChannel, "source_id") == {"sources.id"}
    assert {"requires_auth", "requires_agreement", "next_action"}.issubset(
        ProviderChannel.__table__.columns.keys()
    )


def test_rental_projects_are_context_not_synthetic_events() -> None:
    assert issubclass(HomeQPublicUppsalaProjectAdapter, RentalDevelopmentAdapter)
    assert not issubclass(HomeQPublicUppsalaProjectAdapter, SourceAdapter)
    assert foreign_key_targets(RentalProject, "raw_item_id") == {"raw_items.id"}
    assert "property_id" not in RentalProject.__table__.columns
    assert foreign_key_targets(RentalListing, "rental_project_id") == {"rental_projects.id"}


def test_product_signal_query_requires_live_listing_evidence() -> None:
    query = str(DashboardRepository(None).signal_query())
    assert "EXISTS" in query
    assert "rental_listings.data_mode" in query


def test_internal_signal_query_can_include_historical_test_data() -> None:
    query = str(DashboardRepository(None).signal_query(product_only=False))
    assert "rental_listings.data_mode" not in query


def test_pilot_signal_query_is_live_active_dated_and_time_bounded() -> None:
    query = str(
        DashboardRepository(None).pilot_signal_query(
            policy=PilotCohortPolicy(),
            as_of=date(2026, 9, 1),
            score_run_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        )
    )

    assert "rental_listings.data_mode" in query
    assert "signals.status" in query
    assert "signals.created_at" in query
    assert "rental_listings.available_from" in query
    assert "_available_from" in query
    assert "active_signal_dimensions.run_id" in query


def test_pilot_signal_query_applies_product_and_metric_geo_filters() -> None:
    query = str(
        DashboardRepository(None).pilot_signal_query(
            policy=PilotCohortPolicy(),
            as_of=date(2026, 9, 1),
            filters=PilotSignalFilters(
                address_query="Vaksala",
                strength_band="HIGH",
                min_rooms=3,
                min_area_m2=60,
                center_latitude=59.8586,
                center_longitude=17.6389,
                radius_km=10,
            ),
        )
    )

    assert "signal_strength" in query
    assert "normalized_address" in query
    assert "properties.rooms" in query
    assert "properties.area_m2" in query
    assert "ST_DWithin" in query


def test_pilot_review_filter_is_scoped_to_the_exact_participant_snapshot() -> None:
    query = str(
        DashboardRepository(None).pilot_signal_query(
            policy=PilotCohortPolicy(),
            as_of=date(2026, 9, 1),
            score_run_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            pilot_key="pilot-01",
            filters=PilotSignalFilters(review_status="REVIEWED"),
        )
    )

    assert "pilot_signal_feedback" in query
    assert "pilot_key" in query
    assert "cohort_version" in query
    assert "dimension_scope_key" in query
    assert "score_run_id" in query
    assert "cohort_as_of_date" in query


def test_pilot_pagination_has_a_unique_deterministic_tie_breaker() -> None:
    class SummaryResult:
        @staticmethod
        def one():
            return (0, 0, 0, 0, 0, 0)

    class ScalarResult:
        @staticmethod
        def unique():
            return []

    class RecordingSession:
        item_statement = None

        @staticmethod
        def execute(_statement):
            return SummaryResult()

        def scalars(self, statement):
            self.item_statement = statement
            return ScalarResult()

    session = RecordingSession()
    DashboardRepository(session).pilot_signals(  # type: ignore[arg-type]
        policy=PilotCohortPolicy(),
        as_of=date(2026, 9, 1),
    )

    order_by = str(session.item_statement._order_by_clause)
    assert "_active_strength" in order_by
    assert "signals.created_at" in order_by
    assert "signals.id" in order_by


def test_pilot_sort_options_have_explicit_stable_ordering() -> None:
    class SummaryResult:
        @staticmethod
        def one():
            return (0, 0, 0, 0, 0, 0)

    class ScalarResult:
        @staticmethod
        def unique():
            return []

    class RecordingSession:
        item_statement = None

        @staticmethod
        def execute(_statement):
            return SummaryResult()

        def scalars(self, statement):
            self.item_statement = statement
            return ScalarResult()

    expected = {
        "PRIORITY": "_active_strength",
        "MOVE_WINDOW": "_available_from",
        "NEWEST": "signals.created_at",
    }
    for sort, leading_column in expected.items():
        session = RecordingSession()
        DashboardRepository(session).pilot_signals(  # type: ignore[arg-type]
            policy=PilotCohortPolicy(),
            as_of=date(2026, 9, 1),
            sort=sort,  # type: ignore[arg-type]
        )
        order_by = str(session.item_statement._order_by_clause)
        if sort == "MOVE_WINDOW":
            assert "rental_listings.available_from" in order_by
        else:
            assert order_by.startswith(leading_column)
        assert "signals.id" in order_by


def test_pilot_feedback_keeps_signal_and_version_provenance() -> None:
    assert foreign_key_targets(PilotSignalFeedback, "signal_id") == {"signals.id"}
    assert {
        "pilot_key",
        "cohort_version",
        "dimension_scope_key",
        "score_run_id",
        "score_as_of_date",
        "definition_set_hash",
        "signal_strength_at_review",
        "data_confidence_at_review",
        "timing_at_review",
        "score_rule_version",
        "cohort_as_of_date",
        "score_at_review",
        "verdict",
        "reason",
        "reviewed_at",
    } <= set(PilotSignalFeedback.__table__.columns.keys())


def test_pilot_activity_is_unique_per_signal_snapshot_and_type() -> None:
    assert foreign_key_targets(PilotSignalActivity, "signal_id") == {"signals.id"}
    assert {
        "pilot_key",
        "cohort_version",
        "dimension_scope_key",
        "score_run_id",
        "score_as_of_date",
        "definition_set_hash",
        "signal_strength_at_activity",
        "data_confidence_at_activity",
        "timing_at_activity",
        "score_rule_version",
        "cohort_as_of_date",
        "activity_type",
        "occurrence_count",
        "first_occurred_at",
        "last_occurred_at",
    } <= set(PilotSignalActivity.__table__.columns.keys())


def test_manual_validation_is_separate_from_signal_state() -> None:
    assert foreign_key_targets(SignalValidation, "signal_id") == {"signals.id"}
    assert foreign_key_targets(SignalValidation, "batch_id") == {"validation_batches.id"}
    assert foreign_key_targets(ValidationBatch, "city_id") == {"cities.id"}
    assert "status" in ValidationBatch.__table__.columns
    assert "status" not in SignalValidation.__table__.columns
