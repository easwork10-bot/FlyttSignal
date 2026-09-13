import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from flyttsignal.db.repositories.dashboard import DashboardRepository, PilotSignalSummary
from flyttsignal.db.repositories.pilot_feedback import PilotFeedbackRepository
from flyttsignal.db.repositories.quality import QualityDataset, QualityRepository
from flyttsignal.db.repositories.score_activations import ScoreActivationRepository
from flyttsignal.db.repositories.score_runs import ScoreRunRepository
from flyttsignal.db.repositories.validation import ValidationRepository
from flyttsignal.main import app

client = TestClient(app)

ACTIVE_PILOT_CONTEXT = SimpleNamespace(
    scope_key="internal-pilot",
    city_id=1,
    run_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
    as_of_date=datetime(2026, 9, 8).date(),
    definition_set_hash="a" * 64,
)
EMPTY_PILOT_SUMMARY = PilotSignalSummary(0, 0, 0, 0, 0, 0)


def active_pilot_params() -> dict[str, str]:
    return {
        "cohort_version": "pilot-cohort-v1",
        "cohort_as_of_date": "2026-09-01",
        "dimension_scope_key": "internal-pilot",
        "score_run_id": str(ACTIVE_PILOT_CONTEXT.run_id),
        "score_as_of_date": "2026-09-08",
        "definition_set_hash": "a" * 64,
    }


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_score_runs_are_not_mislabelled_as_a_serving_mode(monkeypatch) -> None:
    run = SimpleNamespace(
        id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        city_id=1,
        as_of_date=datetime(2026, 9, 8).date(),
        feature_schema_revision="signal-features/example",
        definition_set_hash="a" * 64,
        population_fingerprint="b" * 64,
        population_size=3,
        status="COMPLETE",
        created_at=datetime(2026, 9, 8),
    )
    monkeypatch.setattr(ScoreRunRepository, "dimension_runs", lambda *args, **kwargs: [run])

    response = client.get("/api/score-runs?city_id=1")

    assert response.status_code == 200
    assert "serving_mode" not in response.json()[0]
    assert response.json()[0]["population_size"] == 3


def test_active_score_scope_is_explicitly_internal_pilot(monkeypatch) -> None:
    run_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
    run = SimpleNamespace(
        id=run_id,
        city_id=1,
        as_of_date=datetime(2026, 9, 8).date(),
        feature_schema_revision="signal-features/example",
    )
    rows = []
    for index, dimension in enumerate(("DATA_CONFIDENCE", "SIGNAL_STRENGTH", "TIMING"), start=1):
        definition_id = uuid.UUID(f"00000000-0000-0000-0000-{index:012d}")
        activation = SimpleNamespace(
            scope_type="INTERNAL_PILOT",
            scope_key="internal-pilot",
            city_id=1,
            dimension=dimension,
            definition_id=definition_id,
            decision_run_id=run_id,
            activated_at=datetime(2026, 9, 8),
            decision_reason="Reviewed internal pilot prioritization decision.",
        )
        definition = SimpleNamespace(
            id=definition_id,
            dimension=dimension,
            definition_revision="candidate",
            parameter_hash="a" * 64,
            feature_schema_revision="signal-features/example",
            engine_revision="engine/example",
            status="CANDIDATE",
        )
        rows.append((activation, definition, run))
    monkeypatch.setattr(
        ScoreActivationRepository,
        "active_score_activations",
        lambda *args, **kwargs: rows,
    )

    response = client.get("/api/score-activations/internal-pilot?city_id=1")

    assert response.status_code == 200
    assert response.json()["serving_mode"] == "INTERNAL_PILOT"
    assert {item["dimension"] for item in response.json()["activations"]} == {
        "DATA_CONFIDENCE",
        "SIGNAL_STRENGTH",
        "TIMING",
    }


def test_incomplete_dimension_score_set_fails_closed(monkeypatch) -> None:
    run_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
    signal_id = uuid.UUID("20000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(
        ScoreRunRepository,
        "dimension_run",
        lambda *args, **kwargs: SimpleNamespace(id=run_id, as_of_date=datetime(2026, 9, 8).date()),
    )
    monkeypatch.setattr(ScoreRunRepository, "dimension_results", lambda *args, **kwargs: [])

    response = client.get(f"/api/score-runs/{run_id}/signals/{signal_id}")

    assert response.status_code == 404


def test_inconsistent_dimension_score_set_fails_closed(monkeypatch) -> None:
    run_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
    signal_id = uuid.UUID("20000000-0000-0000-0000-000000000001")
    snapshot_id = uuid.UUID("30000000-0000-0000-0000-000000000001")
    run = SimpleNamespace(
        id=run_id,
        as_of_date=datetime(2026, 9, 8).date(),
        feature_schema_revision="signal-features/example",
    )
    result = SimpleNamespace(
        dimension="SIGNAL_STRENGTH",
        score=60,
        components=[],
        warnings=[],
    )
    definition = SimpleNamespace(
        dimension="TIMING",
        feature_schema_revision="signal-features/example",
    )
    snapshot = SimpleNamespace(
        id=snapshot_id,
        signal_id=signal_id,
        as_of_date=run.as_of_date,
        feature_schema_revision="signal-features/example",
        payload_hash="c" * 64,
    )
    monkeypatch.setattr(ScoreRunRepository, "dimension_run", lambda *args, **kwargs: run)
    monkeypatch.setattr(
        ScoreRunRepository,
        "dimension_results",
        lambda *args, **kwargs: [(result, definition, snapshot)] * 3,
    )

    response = client.get(f"/api/score-runs/{run_id}/signals/{signal_id}")

    assert response.status_code == 409


def test_signals_empty(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "signals", lambda *args, **kwargs: [])
    response = client.get("/api/signals")
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


def test_pilot_signals_expose_versioned_live_cohort(monkeypatch) -> None:
    monkeypatch.setattr(
        DashboardRepository,
        "pilot_signals",
        lambda *args, **kwargs: ([], EMPTY_PILOT_SUMMARY),
    )
    monkeypatch.setattr(
        ScoreActivationRepository,
        "active_dimension_context",
        lambda *args, **kwargs: ACTIVE_PILOT_CONTEXT,
    )

    response = client.get("/api/pilot/signals?as_of=2026-09-01")

    assert response.status_code == 200
    body = response.json()
    assert body["cohort_version"] == "pilot-cohort-v1"
    assert body["cohort_as_of_date"] == "2026-09-01"
    assert body["dimension_scope_key"] == "internal-pilot"
    assert body["score_run_id"] == str(ACTIVE_PILOT_CONTEXT.run_id)
    assert body["score_as_of_date"] == "2026-09-08"
    assert body["definition_set_hash"] == "a" * 64
    assert body["criteria"] == {
        "city_id": 1,
        "live_evidence_required": True,
        "active_signals_only": True,
        "dated_signals_only": True,
        "signal_age_days": 28,
        "move_horizon_days": 90,
    }
    assert body["applied_filters"] == {
        "address_query": None,
        "review_status": "ALL",
        "strength_band": None,
        "signal_type": None,
        "date_from": None,
        "date_to": None,
        "property_type": None,
        "min_rooms": None,
        "max_rooms": None,
        "min_area_m2": None,
        "max_area_m2": None,
        "center_latitude": None,
        "center_longitude": None,
        "radius_km": None,
    }
    assert body["sort"] == "PRIORITY"
    assert body["items"] == []
    assert body["count"] == 0
    assert body["total"] == 0
    assert body["summary"] == {
        "total": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "next_30_days": 0,
        "mapped": 0,
    }
    assert body["pagination"] == {
        "limit": 100,
        "offset": 0,
        "has_previous": False,
        "has_next": False,
    }


def test_pilot_signals_normalize_server_search_and_report_pagination(monkeypatch) -> None:
    captured = {}

    def pilot_signals(*args, **kwargs):
        captured.update(kwargs)
        return [], PilotSignalSummary(124, 100, 24, 0, 80, 120)

    monkeypatch.setattr(DashboardRepository, "pilot_signals", pilot_signals)
    monkeypatch.setattr(
        ScoreActivationRepository,
        "active_dimension_context",
        lambda *args, **kwargs: ACTIVE_PILOT_CONTEXT,
    )

    response = client.get(
        "/api/pilot/signals",
        params={
            "address_query": "  Vaksala  ",
            "pilot_key": "pilot-01",
            "review_status": "UNREVIEWED",
            "sort": "NEWEST",
            "limit": 25,
            "offset": 50,
        },
    )

    assert response.status_code == 200
    assert captured["filters"].address_query == "Vaksala"
    assert captured["filters"].review_status == "UNREVIEWED"
    assert captured["pilot_key"] == "pilot-01"
    assert captured["limit"] == 25
    assert captured["offset"] == 50
    assert captured["sort"] == "NEWEST"
    assert response.json()["sort"] == "NEWEST"
    assert response.json()["pagination"] == {
        "limit": 25,
        "offset": 50,
        "has_previous": True,
        "has_next": True,
    }


def test_pilot_signals_reject_invalid_pagination() -> None:
    assert client.get("/api/pilot/signals?limit=501").status_code == 422
    assert client.get("/api/pilot/signals?offset=-1").status_code == 422
    assert client.get("/api/pilot/signals?sort=POPULAR").status_code == 422
    assert client.get("/api/pilot/signals?review_status=REVIEWED").status_code == 422


def test_pilot_signals_reject_incomplete_or_inverted_filters() -> None:
    assert client.get("/api/pilot/signals?radius_km=10").status_code == 422
    assert client.get("/api/pilot/signals?min_rooms=4&max_rooms=2").status_code == 422
    assert client.get("/api/pilot/signals?from=2026-09-10&to=2026-09-01").status_code == 422
    assert client.get("/api/pilot/signals?address_query=%20%20").status_code == 422


def test_pilot_feedback_lookup_can_be_empty(monkeypatch) -> None:
    monkeypatch.setattr(PilotFeedbackRepository, "feedback", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ScoreActivationRepository,
        "active_dimension_context",
        lambda *args, **kwargs: ACTIVE_PILOT_CONTEXT,
    )
    signal_id = uuid.uuid4()

    response = client.get(
        f"/api/pilot/signals/{signal_id}/feedback",
        params={
            "pilot_key": "pilot-01",
            **active_pilot_params(),
        },
    )

    assert response.status_code == 200
    assert response.json() is None


def test_pilot_feedback_rejects_stale_dimension_context(monkeypatch) -> None:
    monkeypatch.setattr(
        ScoreActivationRepository,
        "active_dimension_context",
        lambda *args, **kwargs: ACTIVE_PILOT_CONTEXT,
    )
    params = active_pilot_params()
    params["definition_set_hash"] = "b" * 64

    response = client.get(
        f"/api/pilot/signals/{uuid.uuid4()}/feedback",
        params={"pilot_key": "pilot-01", **params},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == ("Pilot context no longer matches the active dimension run")


def test_pilot_feedback_rejects_mismatched_verdict_and_reason() -> None:
    response = client.put(
        f"/api/pilot/signals/{uuid.uuid4()}/feedback",
        json={
            "pilot_key": "pilot-01",
            **active_pilot_params(),
            "verdict": "USEFUL",
            "reason": "WEAK_SIGNAL",
        },
    )

    assert response.status_code == 422


def test_pilot_activity_rejects_duplicate_signal_ids() -> None:
    signal_id = str(uuid.uuid4())
    response = client.put(
        "/api/pilot/activity",
        json={
            "pilot_key": "pilot-01",
            **active_pilot_params(),
            "activity_type": "SHOWN",
            "signal_ids": [signal_id, signal_id],
        },
    )

    assert response.status_code == 422


def test_spatial_features_empty(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "spatial_features", lambda *args, **kwargs: [])
    response = client.get("/api/spatial-features")
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


def test_rental_listings_empty(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "rental_listings", lambda *args, **kwargs: [])
    response = client.get("/api/rental-listings")
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


def test_rental_listings_reject_unknown_data_mode() -> None:
    response = client.get("/api/rental-listings?data_mode=unknown")
    assert response.status_code == 422


def test_housing_providers_empty(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "housing_providers", lambda *args, **kwargs: [])
    response = client.get("/api/housing-providers")
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


def test_rental_projects_empty(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "rental_projects", lambda *args, **kwargs: [])
    response = client.get("/api/rental-projects")
    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


def test_rental_coverage_empty(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "housing_providers", lambda *args, **kwargs: [])
    monkeypatch.setattr(DashboardRepository, "live_provider_inventory", lambda *args, **kwargs: [])
    response = client.get("/api/rental-coverage")
    assert response.status_code == 200
    assert response.json()["known_provider_count"] == 0
    assert response.json()["providers"] == []


def test_signal_not_found(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "signal", lambda *args, **kwargs: None)
    response = client.get(f"/api/signals/{uuid.uuid4()}")
    assert response.status_code == 404


def test_signal_outcomes_empty(monkeypatch) -> None:
    signal_id = uuid.uuid4()
    monkeypatch.setattr(
        DashboardRepository,
        "signal",
        lambda *args, **kwargs: SimpleNamespace(id=signal_id),
    )
    monkeypatch.setattr(DashboardRepository, "signal_outcomes", lambda *args, **kwargs: [])

    response = client.get(f"/api/signals/{signal_id}/outcomes")

    assert response.status_code == 200
    assert response.json() == []


def test_outcome_summary_distinguishes_observed_from_confirmed(monkeypatch) -> None:
    signal_a = uuid.uuid4()
    signal_b = uuid.uuid4()
    outcomes = [
        SimpleNamespace(
            signal_id=signal_a,
            outcome_type="LISTING_REMOVED",
            subject="LISTING",
            verification_level="OBSERVED",
        ),
        SimpleNamespace(
            signal_id=signal_a,
            outcome_type="CROSS_SOURCE_CONFIRMED",
            subject="SIGNAL",
            verification_level="OBSERVED",
        ),
        SimpleNamespace(
            signal_id=signal_b,
            outcome_type="CONFIRMED_MOVE",
            subject="HOUSEHOLD_MOVE",
            verification_level="CONFIRMED",
        ),
    ]
    monkeypatch.setattr(
        DashboardRepository,
        "signal_outcome_population",
        lambda *args, **kwargs: (10, outcomes),
    )

    response = client.get("/api/outcomes/summary")

    assert response.status_code == 200
    body = response.json()
    assert datetime.fromisoformat(body["generated_at"]).tzinfo is not None
    assert body["signal_population_count"] == 10
    assert body["signals_with_outcomes"] == 2
    assert body["outcome_count"] == 3
    assert body["confirmed_move_count"] == 1
    assert len(body["items"]) == 3


def test_quality_summary_empty_population(monkeypatch) -> None:
    monkeypatch.setattr(
        QualityRepository,
        "dataset",
        lambda *args, **kwargs: QualityDataset(
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
        ),
    )

    response = client.get("/api/quality/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["rule_version"] == "quality-v2"
    assert body["listing_population_count"] == 0
    assert body["classification_coverage"]["percent"] is None


def test_quality_summary_city_not_found(monkeypatch) -> None:
    monkeypatch.setattr(QualityRepository, "dataset", lambda *args, **kwargs: None)

    response = client.get("/api/quality/summary?city_id=999")

    assert response.status_code == 404


def test_retired_score_comparison_routes_are_not_exposed() -> None:
    run_id = uuid.uuid4()
    signal_id = uuid.uuid4()

    assert client.get("/api/score-evaluations").status_code == 404
    assert client.get(f"/api/score-evaluations/{run_id}").status_code == 404
    assert client.get(f"/api/score-evaluations/{run_id}/signals/{signal_id}").status_code == 404


def test_validation_batches_report_review_progress(monkeypatch) -> None:
    batch_id = uuid.uuid4()
    batch = SimpleNamespace(
        id=batch_id,
        name="batch",
        city_id=1,
        rule_version="validation-v1",
        dimension_scope_key=None,
        score_run_id=None,
        score_as_of_date=None,
        definition_set_hash=None,
        seed="seed",
        target_size=2,
        population_size=10,
        status="IN_REVIEW",
        validations=[
            SimpleNamespace(review_status="REVIEWED", verdict="GOOD", issue_codes=[]),
            SimpleNamespace(review_status="PENDING", verdict=None, issue_codes=[]),
        ],
        created_at=datetime.now().astimezone(),
        completed_at=None,
    )
    monkeypatch.setattr(ValidationRepository, "batches", lambda *args, **kwargs: [batch])

    response = client.get("/api/validation-batches")

    assert response.status_code == 200
    assert response.json()[0]["reviewed_count"] == 1
    assert response.json()[0]["pending_count"] == 1
    assert response.json()[0]["verdict_counts"] == {"GOOD": 1}


def test_validation_batch_not_found(monkeypatch) -> None:
    monkeypatch.setattr(ValidationRepository, "batch", lambda *args, **kwargs: None)

    response = client.get(f"/api/validation-batches/{uuid.uuid4()}")

    assert response.status_code == 404


def test_lifecycle_readiness_reports_no_scheduled_runs(monkeypatch) -> None:
    source_id = uuid.uuid4()
    monkeypatch.setattr(
        DashboardRepository,
        "source_by_key",
        lambda *args, **kwargs: SimpleNamespace(id=source_id, key="test-source"),
    )
    monkeypatch.setattr(DashboardRepository, "source_runs", lambda *args, **kwargs: [])

    response = client.get("/api/sources/test-source/lifecycle-readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "NOT_READY"
    assert response.json()["reasons"] == ["no_scheduled_runs"]


def test_lifecycle_readiness_source_not_found(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "source_by_key", lambda *args, **kwargs: None)

    response = client.get("/api/sources/missing/lifecycle-readiness")

    assert response.status_code == 404


def test_rental_listing_classifications_empty(monkeypatch) -> None:
    listing_id = uuid.uuid4()
    monkeypatch.setattr(
        DashboardRepository,
        "rental_listing",
        lambda *args, **kwargs: SimpleNamespace(id=listing_id),
    )
    monkeypatch.setattr(
        DashboardRepository,
        "rental_listing_classifications",
        lambda *args, **kwargs: [],
    )

    response = client.get(f"/api/rental-listings/{listing_id}/classifications")

    assert response.status_code == 200
    assert response.json() == []


def test_rental_listing_classifications_not_found(monkeypatch) -> None:
    monkeypatch.setattr(DashboardRepository, "rental_listing", lambda *args, **kwargs: None)

    response = client.get(f"/api/rental-listings/{uuid.uuid4()}/classifications")

    assert response.status_code == 404


def test_rental_listing_measurements_empty(monkeypatch) -> None:
    listing_id = uuid.uuid4()
    monkeypatch.setattr(
        DashboardRepository,
        "rental_listing",
        lambda *args, **kwargs: SimpleNamespace(id=listing_id),
    )
    monkeypatch.setattr(
        DashboardRepository,
        "rental_listing_measurements",
        lambda *args, **kwargs: [],
    )

    response = client.get(f"/api/rental-listings/{listing_id}/measurements")

    assert response.status_code == 200
    assert response.json() == []


def test_lead_time_summary_includes_population_and_missing_measurements(monkeypatch) -> None:
    measured = SimpleNamespace(status="MEASURED", value=Decimal("10"))
    missing_input = SimpleNamespace(status="MISSING_INPUT", value=None)
    late = SimpleNamespace(status="MEASURED", value=Decimal("-2"))
    monkeypatch.setattr(
        DashboardRepository,
        "lead_time_population",
        lambda *args, **kwargs: [
            (SimpleNamespace(), measured),
            (SimpleNamespace(), missing_input),
            (SimpleNamespace(), late),
            (SimpleNamespace(), None),
        ],
    )

    response = client.get("/api/measurements/lead-time")

    assert response.status_code == 200
    body = response.json()
    assert body["population_count"] == 4
    assert body["measurement_count"] == 3
    assert body["measured_count"] == 2
    assert body["missing_input_count"] == 1
    assert body["late_count"] == 1
    assert body["median_days"] == "4"
