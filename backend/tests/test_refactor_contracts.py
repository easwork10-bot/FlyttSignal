import ast
import json
import re
from pathlib import Path

from sqlalchemy.orm import configure_mappers

import flyttsignal.db.models as model_facade
from flyttsignal.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "backend" / "src" / "flyttsignal"
WEB_ROOT = PROJECT_ROOT / "apps" / "web" / "src"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
RETIRED_API_SCHEMAS = {
    "QualityScoreBucketOut",
    "ScoreComponentOut",
    "ScoreEvaluationRunOut",
    "SignalScoreEvaluationOut",
}
CANONICAL_OPERATION_IDS = {
    "checkHealth",
    "getActiveSignalDimensions",
    "getLeadTimeSummary",
    "getOutcomeSummary",
    "getPilotMetrics",
    "getPilotSignalFeedback",
    "getProperty",
    "getQualitySummary",
    "getRentalCoverage",
    "getScoreActivationSet",
    "getScoreRun",
    "getScoreRunSignalDimensions",
    "getSignal",
    "getSourceLifecycleReadiness",
    "getValidationBatch",
    "listCities",
    "listHousingProviders",
    "listPilotSignals",
    "listRentalListingClassifications",
    "listRentalListingMeasurements",
    "listRentalListings",
    "listRentalProjects",
    "listScoreRuns",
    "listSignalOutcomes",
    "listSignals",
    "listSourceRuns",
    "listSources",
    "listSpatialFeatures",
    "listValidationBatches",
    "recordPilotActivity",
    "upsertPilotSignalFeedback",
}


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name for alias in node.names if alias.name.startswith("flyttsignal")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("flyttsignal"):
                imports.add(node.module)
    return imports


def _top_level_definitions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _assert_layer_excludes(layer: str, forbidden: tuple[str, ...]) -> None:
    layer_root = PACKAGE_ROOT / layer
    if not layer_root.exists():
        return
    violations: list[str] = []
    for path in sorted(layer_root.rglob("*.py")):
        for imported in sorted(_internal_imports(path)):
            if any(imported == name or imported.startswith(f"{name}.") for name in forbidden):
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} -> {imported}")
    assert not violations, "Forbidden dependency direction:\n" + "\n".join(violations)


def test_openapi_contract_uses_canonical_paths_names_and_schemas() -> None:
    actual = app.openapi()

    assert all(path.startswith("/api/") for path in actual["paths"])
    assert not [path for path in actual["paths"] if path.startswith("/api/v1/")]
    assert not [path for path in actual["paths"] if "score-evaluations" in path]
    operation_ids = {
        operation["operationId"]
        for path in actual["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operation_ids == CANONICAL_OPERATION_IDS

    actual_schemas = actual["components"]["schemas"]
    actual_signal = actual_schemas["SignalOut"]
    retired_signal_fields = {"score", "score_components"}
    assert retired_signal_fields.isdisjoint(actual_signal["properties"])
    assert actual_signal["properties"]["active_dimensions"] == {
        "$ref": "#/components/schemas/ActiveDimensionsOut"
    }
    assert actual_signal["properties"]["timing"]["anyOf"][0] == {
        "$ref": "#/components/schemas/SignalTimingOut"
    }
    assert RETIRED_API_SCHEMAS.isdisjoint(actual_schemas)
    assert {
        "ScoreRunOut",
        "SignalDimensionEvaluationOut",
        "SignalDimensionSetOut",
    } <= actual_schemas.keys()
    assert {
        "DimensionScoreRunOut",
        "SignalDimensionResultOut",
        "SignalDimensionScoreSetOut",
    }.isdisjoint(actual_schemas)
    assert "serving_mode" not in actual_schemas["ScoreRunOut"]["properties"]
    assert "serving_mode" not in actual_schemas["SignalDimensionSetOut"]["properties"]
    assert "QualityStrengthBucketOut" in actual_schemas
    assert "signal_strength_distribution" in actual_schemas["QualitySummaryOut"][
        "properties"
    ]
    assert {
        "signal_strength_at_selection",
        "data_confidence_at_selection",
        "timing_at_selection",
        "strength_stratum",
    } <= actual_schemas["SignalValidationOut"]["properties"].keys()
    assert {
        "dimension_scope_key",
        "score_run_id",
        "score_as_of_date",
        "definition_set_hash",
    } <= actual_schemas["ValidationBatchSummaryOut"]["properties"].keys()


def test_api_has_no_retired_catch_all_modules() -> None:
    retired = (
        PACKAGE_ROOT / "api" / "routes" / "core.py",
        PACKAGE_ROOT / "api" / "service.py",
        PACKAGE_ROOT / "schemas" / "api.py",
    )
    assert not [path.relative_to(PROJECT_ROOT) for path in retired if path.exists()]


def test_score_run_runtime_has_explicit_boundaries() -> None:
    retired = (
        PACKAGE_ROOT / "api" / "routes" / "score_evaluations.py",
        PACKAGE_ROOT / "api" / "schemas" / "score_evaluations.py",
        PACKAGE_ROOT / "db" / "repositories" / "scoring.py",
    )
    canonical = (
        PACKAGE_ROOT / "api" / "routes" / "score_runs.py",
        PACKAGE_ROOT / "api" / "routes" / "score_activations.py",
        PACKAGE_ROOT / "api" / "schemas" / "score_runs.py",
        PACKAGE_ROOT / "api" / "schemas" / "score_activations.py",
        PACKAGE_ROOT / "db" / "repositories" / "score_runs.py",
        PACKAGE_ROOT / "db" / "repositories" / "score_activations.py",
        PACKAGE_ROOT / "scoring" / "read_models.py",
    )
    assert not [path.relative_to(PROJECT_ROOT) for path in retired if path.exists()]
    assert all(path.is_file() for path in canonical)


def test_completed_domain_slices_have_no_legacy_module() -> None:
    retired = (
        PACKAGE_ROOT / "events" / "service.py",
        PACKAGE_ROOT / "matching" / "service.py",
        PACKAGE_ROOT / "signals" / "service.py",
        PACKAGE_ROOT / "scoring" / "service.py",
        PACKAGE_ROOT / "validation" / "service.py",
        PACKAGE_ROOT / "projects" / "service.py",
        PACKAGE_ROOT / "providers" / "identity.py",
    )
    assert not [path.relative_to(PROJECT_ROOT) for path in retired if path.exists()]


def test_listing_rules_are_not_duplicated_in_orchestration_modules() -> None:
    retired_definitions = {
        PACKAGE_ROOT / "classification" / "service.py": {"Classification", "classify_listing"},
        PACKAGE_ROOT / "measurements" / "service.py": {"Measurement", "measure_lead_time"},
        PACKAGE_ROOT / "lifecycle" / "listings.py": {
            "ListingLifecyclePolicy",
            "ListingLifecycleResult",
            "listing_status_after_miss",
        },
        PACKAGE_ROOT / "ingestion" / "pipelines" / "rental_listings.py": {
            "listing_status_after_miss"
        },
    }
    violations = {
        str(path.relative_to(PROJECT_ROOT)): sorted(names & _top_level_definitions(path))
        for path, names in retired_definitions.items()
        if names & _top_level_definitions(path)
    }
    assert not violations


def test_property_rules_are_not_duplicated_in_remediation_modules() -> None:
    path = PACKAGE_ROOT / "property_provenance" / "service.py"
    domain_owned = {
        "ListingIdentity",
        "PropertyIdentity",
        "MatchStrength",
        "PropertyFingerprint",
        "MatchDecision",
        "classify_property_match",
        "choose_strong_match",
    }
    assert not domain_owned & _top_level_definitions(path)


def test_signal_rules_are_not_duplicated_in_persistence_modules() -> None:
    retired_definitions = {
        PACKAGE_ROOT / "outcomes" / "service.py": {
            "OutcomeDefinition",
        },
        PACKAGE_ROOT / "db" / "repositories" / "validation.py": {
            "ValidationCandidate",
        },
    }
    violations = {
        str(path.relative_to(PROJECT_ROOT)): sorted(names & _top_level_definitions(path))
        for path, names in retired_definitions.items()
        if path.exists() and names & _top_level_definitions(path)
    }
    assert not violations


def test_development_model_is_not_duplicated_in_integration_modules() -> None:
    paths = (
        PACKAGE_ROOT / "ingestion" / "contracts.py",
        PACKAGE_ROOT / "integrations" / "sources" / "rental_developments" / "homeq.py",
        PACKAGE_ROOT / "ingestion" / "pipelines" / "rental_developments.py",
    )
    duplicates = {
        str(path.relative_to(PROJECT_ROOT)): sorted(
            {"RentalProjectInput", "RentalDevelopment"} & _top_level_definitions(path)
        )
        for path in paths
        if {"RentalProjectInput", "RentalDevelopment"} & _top_level_definitions(path)
    }
    assert not duplicates


def test_ingestion_contracts_and_snapshot_policy_are_separate() -> None:
    contracts = PACKAGE_ROOT / "ingestion" / "contracts.py"
    snapshot_policy = PACKAGE_ROOT / "ingestion" / "snapshot_integrity.py"
    assert not (PACKAGE_ROOT / "collectors" / "base.py").exists()
    assert not {
        "SnapshotStatus",
        "SnapshotAssessment",
        "assess_snapshot",
    } & _top_level_definitions(contracts)
    assert {"SnapshotStatus", "SnapshotAssessment", "assess_snapshot"} <= (
        _top_level_definitions(snapshot_policy)
    )

    forbidden = (
        "flyttsignal.api",
        "flyttsignal.collectors",
        "flyttsignal.db",
        "flyttsignal.integrations",
        "flyttsignal.worker",
    )
    violations = {
        str(path.relative_to(PROJECT_ROOT)): sorted(
            imported
            for imported in _internal_imports(path)
            if any(imported == name or imported.startswith(f"{name}.") for name in forbidden)
        )
        for path in (contracts, snapshot_policy)
        if any(
            imported == name or imported.startswith(f"{name}.")
            for imported in _internal_imports(path)
            for name in forbidden
        )
    }
    assert not violations


def test_ingestion_pipelines_are_not_worker_owned() -> None:
    pipelines = {
        "rental_listings.py": ("pipeline.py", "execute_rental_listing_source"),
        "benchmark_statistics.py": (
            "benchmark_pipeline.py",
            "execute_benchmark_statistics_source",
        ),
        "address_enrichment.py": (
            "enrichment_pipeline.py",
            "execute_address_enrichment_source",
        ),
        "spatial_features.py": ("spatial_pipeline.py", "execute_spatial_feature_source"),
        "rental_developments.py": (
            "project_pipeline.py",
            "execute_rental_development_source",
        ),
    }
    violations: list[str] = []
    for filename, (retired_worker_module, entrypoint) in pipelines.items():
        pipeline = PACKAGE_ROOT / "ingestion" / "pipelines" / filename
        if (PACKAGE_ROOT / "worker" / retired_worker_module).exists():
            violations.append(f"legacy worker module: {retired_worker_module}")
        if entrypoint not in _top_level_definitions(pipeline):
            violations.append(f"missing {filename}: {entrypoint}")
        worker_imports = sorted(
            imported
            for imported in _internal_imports(pipeline)
            if imported == "flyttsignal.worker" or imported.startswith("flyttsignal.worker.")
        )
        violations.extend(f"{filename} -> {imported}" for imported in worker_imports)

    assert not (PACKAGE_ROOT / "worker" / "hashing.py").exists()
    assert not violations


def test_housing_provider_identity_is_not_duplicated_in_integration_modules() -> None:
    paths = (
        PACKAGE_ROOT / "integrations" / "sources" / "rental_listings" / "homeq.py",
        PACKAGE_ROOT
        / "integrations"
        / "sources"
        / "rental_listings"
        / "uppsala_bostadsformedling.py",
    )
    duplicates = {
        str(path.relative_to(PROJECT_ROOT)): sorted(
            {"canonical_provider_key"} & _top_level_definitions(path)
        )
        for path in paths
        if {"canonical_provider_key"} & _top_level_definitions(path)
    }
    assert not duplicates


def test_migrations_have_one_canonical_baseline() -> None:
    from alembic.script import ScriptDirectory

    migrations = PROJECT_ROOT / "backend" / "migrations"
    script = ScriptDirectory(str(migrations))
    assert script.get_bases() == ["0001_baseline"]
    assert len(script.get_heads()) == 1
    baseline = script.get_revision("0001_baseline")
    assert baseline.down_revision is None
    sql = (migrations / "baseline.sql").read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in sql
    assert "CREATE TRIGGER rental_listing_revisions_append_only" in sql
    assert "INSERT INTO public.sources" in sql
    assert "CURRENT_TIMESTAMP" in sql


def test_database_models_have_a_package_boundary() -> None:
    model_root = PACKAGE_ROOT / "db" / "models"
    assert model_root.is_dir()
    assert not (PACKAGE_ROOT / "db" / "models.py").exists()
    foundation = {"Base", "SourceType", "Scope", "RunStatus", "RunTrigger", "uuid_pk", "now"}
    assert foundation <= _top_level_definitions(model_root / "base.py")
    assert foundation.isdisjoint(_top_level_definitions(model_root / "__init__.py"))
    source_models = {"City", "Source", "SourceCity", "SourceRun", "RawItem"}
    assert source_models <= _top_level_definitions(model_root / "sources.py")
    assert source_models.isdisjoint(_top_level_definitions(model_root / "__init__.py"))
    assert {"BenchmarkObservation"} <= _top_level_definitions(
        model_root / "benchmark_statistics.py"
    )
    assert {"SpatialFeature"} <= _top_level_definitions(model_root / "spatial_features.py")
    assert {"BenchmarkObservation", "SpatialFeature"}.isdisjoint(
        _top_level_definitions(model_root / "__init__.py")
    )
    property_models = {"Address", "AddressEnrichment", "AddressRegisterUnitLink", "Property"}
    assert property_models <= _top_level_definitions(model_root / "properties.py")
    assert property_models.isdisjoint(_top_level_definitions(model_root / "__init__.py"))
    provider_models = {"HousingProvider", "HousingProviderCity", "ProviderChannel"}
    assert provider_models <= _top_level_definitions(model_root / "housing_providers.py")
    development_models = {"RentalProject"}
    assert development_models <= _top_level_definitions(model_root / "rental_developments.py")
    listing_models = {"RentalListing", "RentalListingClassification", "ListingMeasurement"}
    assert listing_models <= _top_level_definitions(model_root / "rental_listings.py")
    assert (provider_models | development_models | listing_models).isdisjoint(
        _top_level_definitions(model_root / "__init__.py")
    )
    event_models = {"Event"}
    assert event_models <= _top_level_definitions(model_root / "events.py")
    signal_models = {"Signal", "SignalEvidence", "SignalOutcome", "ScoreComponent"}
    assert signal_models <= _top_level_definitions(model_root / "signals.py")
    validation_models = {"ValidationBatch", "SignalValidation"}
    assert validation_models <= _top_level_definitions(model_root / "signal_validation.py")
    evaluation_models = {
        "ScoreEvaluationRun",
        "SignalFeatureSnapshot",
        "SignalScoreEvaluation",
    }
    assert evaluation_models <= _top_level_definitions(model_root / "score_evaluations.py")
    pilot_models = {"PilotSignalActivity", "PilotSignalFeedback"}
    assert {"PilotSignalActivity"} <= _top_level_definitions(
        model_root / "pilot_activity.py"
    )
    assert {"PilotSignalFeedback"} <= _top_level_definitions(
        model_root / "pilot_feedback.py"
    )
    assert (
        event_models | signal_models | validation_models | evaluation_models | pilot_models
    ).isdisjoint(
        _top_level_definitions(model_root / "__init__.py")
    )


def test_database_model_facade_exposes_the_complete_mapper_graph() -> None:
    configure_mappers()
    mappers = tuple(model_facade.Base.registry.mappers)
    mapped_names = {mapper.class_.__name__ for mapper in mappers}

    assert len(model_facade.Base.metadata.tables) == 35
    assert len(mappers) == 35
    assert {
        "RentalListingRevision",
        "ScoreActivation",
        "ScoreDefinition",
        "ScoreRun",
        "SignalDimensionEvaluation",
    } <= mapped_names
    assert mapped_names <= set(model_facade.__all__)
    assert all(mapper.class_.__module__ != "flyttsignal.db.models" for mapper in mappers)


def test_frontend_route_pages_delegate_to_owned_features() -> None:
    routes = {
        "app/page.tsx": (
            'export { DashboardPage as default } from "@/features/dashboard/dashboard-page";'
        ),
        "app/rentals/page.tsx": (
            'export { RentalsPage as default } from "@/features/rentals/rentals-page";'
        ),
        "app/signals/page.tsx": (
            'export { SignalsPage as default } from "@/features/signals/signals-page";'
        ),
        "app/signals/[id]/page.tsx": (
            'export { SignalDetailPage as default } from "@/features/signals/signal-detail-page";'
        ),
        "app/pilot/page.tsx": (
            'import { Suspense } from "react";\n\n'
            'import { Loading } from "@/components/states";\n'
            'import { PilotPage } from "@/features/pilot/pilot-page";\n\n'
            "export default function PilotRoute() {\n"
            "  return (\n"
            '    <Suspense fallback={<Loading label="Öppnar pilotvyn…" />}>\n'
            "      <PilotPage />\n"
            "    </Suspense>\n"
            "  );\n"
            "}"
        ),
        "app/sources/page.tsx": (
            'export { SourcesPage as default } from "@/features/sources/sources-page";'
        ),
    }
    assert {
        path: (WEB_ROOT / path).read_text(encoding="utf-8").strip() for path in routes
    } == routes


def test_frontend_feature_components_are_not_flat_or_route_owned() -> None:
    retired = {
        "lantmateriet-enrichment-card.tsx",
        "provider-coverage.tsx",
        "signal-map-workspace.tsx",
        "signal-map.tsx",
        "signal-preview.tsx",
        "signal-table.tsx",
        "uppsala-spatial-context.tsx",
    }
    component_root = WEB_ROOT / "components"
    assert retired.isdisjoint(path.name for path in component_root.glob("*.tsx"))

    feature_files = tuple((WEB_ROOT / "features").rglob("*.tsx"))
    assert feature_files
    assert not [
        path.relative_to(WEB_ROOT)
        for path in feature_files
        if 'from "@/app/' in path.read_text(encoding="utf-8")
    ]
    assert not [
        path.relative_to(WEB_ROOT)
        for path in (component_root / "ui").glob("*.tsx")
        if 'from "@/features/' in path.read_text(encoding="utf-8")
    ]


def test_frontend_contract_artifact_matches_fastapi_and_is_generated() -> None:
    artifact = PROJECT_ROOT / "apps" / "web" / "openapi.json"
    package = json.loads(
        (PROJECT_ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    )
    type_facade = (WEB_ROOT / "lib" / "api" / "types.ts").read_text(encoding="utf-8")
    generated_types = WEB_ROOT / "lib" / "api" / "generated.ts"

    assert json.loads(artifact.read_text(encoding="utf-8")) == app.openapi()
    assert "openapi-typescript" in package["devDependencies"]
    assert {"contracts:generate", "contracts:check"} <= package["scripts"].keys()
    assert generated_types.is_file()
    assert 'from "./generated"' in type_facade
    assert "export type Property = {" not in type_facade


def test_api_does_not_depend_on_ingestion_or_worker() -> None:
    _assert_layer_excludes(
        "api",
        (
            "flyttsignal.collectors",
            "flyttsignal.ingestion",
            "flyttsignal.integrations",
            "flyttsignal.worker",
        ),
    )


def test_database_does_not_depend_on_delivery_or_orchestration() -> None:
    _assert_layer_excludes(
        "db",
        (
            "flyttsignal.api",
            "flyttsignal.collectors",
            "flyttsignal.integrations",
            "flyttsignal.worker",
        ),
    )


def test_source_integrations_do_not_depend_on_api_database_or_worker() -> None:
    _assert_layer_excludes(
        "collectors",
        ("flyttsignal.api", "flyttsignal.db", "flyttsignal.worker"),
    )
    _assert_layer_excludes(
        "integrations",
        ("flyttsignal.api", "flyttsignal.db", "flyttsignal.worker"),
    )


def test_rental_source_integrations_are_grouped_by_observation_role() -> None:
    rental_listing_modules = {
        "heimstaden.py",
        "homeq.py",
        "hsb.py",
        "uppsala_bostadsformedling.py",
    }
    listing_root = PACKAGE_ROOT / "integrations" / "sources" / "rental_listings"
    assert rental_listing_modules <= {
        path.name for path in listing_root.glob("*.py") if path.name != "__init__.py"
    }

    listing_definitions = set().union(
        *(_top_level_definitions(listing_root / name) for name in rental_listing_modules)
    )
    assert {
        "UppsalaBostadsformedlingAdapter",
        "HeimstadenUppsalaAdapter",
        "HomeQPublicUppsalaAdapter",
        "HSBPublicUppsalaAdapter",
    } <= listing_definitions
    assert not {
        "UppsalaBostadsformedlingFixtureAdapter",
        "UppsalaBostadsformedlingLiveAdapter",
        "HomeQPublicUppsalaFixtureAdapter",
        "HomeQPublicUppsalaLiveAdapter",
        "HSBPublicUppsalaFixtureAdapter",
        "HSBPublicUppsalaLiveAdapter",
        "FakeUppsalaRentalAdapter",
        "FakeUppsalaPartnerAdapter",
    } & listing_definitions
    development_definitions = _top_level_definitions(
        PACKAGE_ROOT / "integrations" / "sources" / "rental_developments" / "homeq.py"
    )
    assert "HomeQPublicUppsalaProjectAdapter" not in listing_definitions
    assert "HomeQPublicUppsalaAdapter" not in development_definitions

    retired_listing_modules = {
        "synthetic_partner.py",
        "synthetic_uppsala.py",
    }
    assert retired_listing_modules.isdisjoint(
        {path.name for path in listing_root.glob("*.py")}
    )

    retired = (
        PACKAGE_ROOT / "collectors" / "fake",
        PACKAGE_ROOT / "collectors" / "heimstaden",
        PACKAGE_ROOT / "collectors" / "homeq",
        PACKAGE_ROOT / "collectors" / "hsb",
        PACKAGE_ROOT / "collectors" / "uppsala" / "rentals.py",
    )
    assert not [path.relative_to(PROJECT_ROOT) for path in retired if path.exists()]


def test_benchmark_source_integration_is_role_owned() -> None:
    module = PACKAGE_ROOT / "integrations" / "sources" / "benchmark_statistics" / "scb.py"
    assert "SCBMigrationAdapter" in _top_level_definitions(module)
    assert not (PACKAGE_ROOT / "collectors" / "scb").exists()


def test_address_enrichment_source_integration_is_role_owned() -> None:
    module = PACKAGE_ROOT / "integrations" / "sources" / "address_enrichment" / "lantmateriet.py"
    assert "LantmaterietAddressAdapter" in _top_level_definitions(module)
    assert not (PACKAGE_ROOT / "collectors" / "lantmateriet").exists()


def test_spatial_source_integration_is_role_owned_and_collectors_are_retired() -> None:
    module = PACKAGE_ROOT / "integrations" / "sources" / "spatial_features" / "uppsala_open_data.py"
    assert "UppsalaBuildingsAdapter" in _top_level_definitions(module)
    assert not (PACKAGE_ROOT / "collectors").exists()


def test_worker_does_not_depend_on_http_delivery() -> None:
    _assert_layer_excludes("worker", ("flyttsignal.api",))


def test_domain_does_not_depend_on_infrastructure_or_delivery() -> None:
    _assert_layer_excludes(
        "domains",
        (
            "flyttsignal.analytics",
            "flyttsignal.api",
            "flyttsignal.db",
            "flyttsignal.ingestion",
            "flyttsignal.integrations",
            "flyttsignal.worker",
        ),
    )


def test_local_documentation_links_resolve() -> None:
    markdown_files = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "AGENTS.md",
        *sorted((PROJECT_ROOT / "docs").rglob("*.md")),
    ]
    broken: list[str] = []
    for path in markdown_files:
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_path = target.split("#", maxsplit=1)[0]
            if relative_path and not (path.parent / relative_path).resolve().exists():
                broken.append(f"{path.relative_to(PROJECT_ROOT)} -> {target}")
    assert not broken, "Broken local documentation links:\n" + "\n".join(broken)
