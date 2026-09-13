from flyttsignal.db.models.base import RunStatus
from flyttsignal.domains.events.models import EventType
from flyttsignal.domains.listings.classification import CATEGORY_TAGS
from flyttsignal.domains.properties.matching import MatchStrength
from flyttsignal.domains.signals.features import (
    FEATURE_REGISTRY,
    FEATURES_BY_NAME,
    FeatureDimension,
    FeatureUse,
)
from flyttsignal.ingestion.snapshot_integrity import SnapshotStatus


def test_feature_registry_has_unique_complete_contracts() -> None:
    assert len(FEATURES_BY_NAME) == len(FEATURE_REGISTRY)
    assert all(feature.definition for feature in FEATURE_REGISTRY)
    assert all(feature.source for feature in FEATURE_REGISTRY)
    assert all(feature.missing_semantics for feature in FEATURE_REGISTRY)
    assert all(feature.affects.isdisjoint(feature.prohibits) for feature in FEATURE_REGISTRY)


def test_registry_uses_current_domain_vocabularies() -> None:
    assert set(FEATURES_BY_NAME["event_type"].allowed_values) == {
        value.value for value in EventType
    }
    assert set(FEATURES_BY_NAME["property_match"].allowed_values) == {
        value.value for value in MatchStrength
    }
    assert set(FEATURES_BY_NAME["snapshot_status"].allowed_values) == {
        value.value for value in SnapshotStatus
    }
    assert set(FEATURES_BY_NAME["source_run_status"].allowed_values) == {
        value.value for value in RunStatus
    }
    expected_classifications = set(CATEGORY_TAGS.values()) | {"NEW_CONSTRUCTION", "UNKNOWN"}
    assert set(FEATURES_BY_NAME["classification_tags"].allowed_values) == (
        expected_classifications
    )


def test_commercial_size_and_price_cannot_influence_signal_strength() -> None:
    for name in ("rooms", "area_m2", "property_type", "monthly_rent"):
        feature = FEATURES_BY_NAME[name]
        assert FeatureDimension.COMMERCIAL_RELEVANCE in feature.affects
        assert FeatureDimension.SIGNAL_STRENGTH in feature.prohibits


def test_raw_evidence_count_cannot_claim_independence() -> None:
    raw_count = FEATURES_BY_NAME["evidence_count"]
    independent_count = FEATURES_BY_NAME["independent_evidence_count"]
    assert FeatureDimension.SIGNAL_STRENGTH in raw_count.prohibits
    assert FeatureUse.SCORING not in raw_count.uses
    assert FeatureDimension.SIGNAL_STRENGTH in independent_count.affects
    assert FeatureUse.SCORING in independent_count.uses


def test_collection_health_does_not_strengthen_the_move_hypothesis() -> None:
    for name in ("snapshot_status", "source_run_status", "parser_warnings"):
        feature = FEATURES_BY_NAME[name]
        assert FeatureDimension.DATA_CONFIDENCE in feature.affects
        assert FeatureDimension.SIGNAL_STRENGTH in feature.prohibits
