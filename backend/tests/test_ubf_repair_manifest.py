import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.preview_ubf_semantic_repair import build_manifest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "rental_listings"
    / "uppsala_bostadsformedling"
    / "detail-contract.json"
)


def test_manifest_is_bounded_deterministic_and_preserves_history() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    case = contract["cases"][0]
    rows = [
        {
            "listing_id": "listing-1",
            "source_item_id": case["requested_id"],
            "raw_item_id": "raw-1",
            "property_id": "property-1",
            "listing_status": "ACTIVE",
            "provider_key": "klovern",
            "listing_unit_identifier": None,
            "listing_new_construction": False,
            "project_source_item_id": None,
            "property_unit_identifier": None,
            "property_new_construction": False,
            "property_listing_ids": ["listing-1"],
            "event_id": "event-old",
            "event_type": "RENTAL_LISTED",
            "signal_id": "signal-old",
            "signal_type": "LIKELY_TENANT_MOVE_OUT",
            "signal_status": "ACTIVE",
            "evidence_superseded_at": None,
            "signal_current_evidence_count": 1,
            "outcome_ids": ["outcome-1"],
            "feedback_ids": ["feedback-1"],
            "activity_ids": ["activity-1"],
        }
    ]

    manifest = build_manifest(
        {"cases": [case]},
        rows,
        generated_at=datetime(2026, 9, 8, 10, tzinfo=UTC),
        database_revision="0029_feature_snapshots",
    )

    target = manifest["targets"][0]
    assert manifest["mode"] == "read-only-dry-run"
    assert target["disposition"] == "PLANNED"
    assert {action["kind"] for action in target["actions"]} == {
        "UPDATE_LISTING_UNIT_IDENTITY",
        "UPDATE_LISTING_CONSTRUCTION",
        "REUSE_OR_CREATE_NEW_BUILD_CHAIN",
        "SUPERSEDE_EVIDENCE",
    }
    assert target["protected_history"] == {
        "outcome_ids": ["outcome-1"],
        "feedback_ids": ["feedback-1"],
        "activity_ids": ["activity-1"],
    }
    repeat = build_manifest(
        {"cases": [case]},
        rows,
        generated_at=datetime(2026, 9, 8, 10, tzinfo=UTC),
        database_revision="0029_feature_snapshots",
    )
    assert repeat == manifest


def test_manifest_routes_shared_or_removed_records_to_manual_review() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    case = contract["cases"][1]
    row = {
        "listing_id": "listing-2",
        "source_item_id": case["requested_id"],
        "raw_item_id": "raw-2",
        "property_id": "property-2",
        "listing_status": "REMOVED",
        "provider_key": "ubf-landlord-100017249115",
        "listing_unit_identifier": None,
        "listing_new_construction": False,
        "project_source_item_id": None,
        "property_unit_identifier": None,
        "property_new_construction": False,
        "property_listing_ids": ["listing-2", "listing-other"],
        "event_id": None,
        "event_type": None,
        "signal_id": None,
        "signal_type": None,
        "signal_status": None,
        "evidence_superseded_at": None,
        "signal_current_evidence_count": 0,
        "outcome_ids": [],
        "feedback_ids": [],
        "activity_ids": [],
    }

    manifest = build_manifest(
        {"cases": [case]},
        [row],
        generated_at=datetime(2026, 9, 8, 10, tzinfo=UTC),
        database_revision="0029_feature_snapshots",
    )

    assert manifest["manual_review_count"] == 1
    assert manifest["targets"][0]["review_reasons"] == [
        "listing_is_not_active",
        "property_is_shared_by_multiple_listings",
    ]
