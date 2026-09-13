from fastapi import APIRouter

from flyttsignal.api.routes import (
    cities,
    health,
    housing_providers,
    measurements,
    outcomes,
    pilot,
    properties,
    quality,
    rental_coverage,
    rental_developments,
    rental_listings,
    score_activations,
    score_runs,
    signals,
    source_runs,
    sources,
    spatial_features,
    validation_batches,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(cities.router)
router.include_router(sources.router)
router.include_router(housing_providers.router)
router.include_router(source_runs.router)
router.include_router(rental_developments.router)
router.include_router(rental_coverage.router)
router.include_router(spatial_features.router)
router.include_router(rental_listings.router)
router.include_router(measurements.router)
router.include_router(signals.router)
router.include_router(outcomes.router)
router.include_router(pilot.router)
router.include_router(quality.router)
router.include_router(score_runs.router)
router.include_router(score_activations.router)
router.include_router(validation_batches.router)
router.include_router(properties.router)
