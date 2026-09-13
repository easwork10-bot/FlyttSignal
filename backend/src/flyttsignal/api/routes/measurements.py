import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.measurements import LeadTimeSummaryOut, ListingMeasurementOut
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/rental-listings/{listing_id}/measurements",
    response_model=list[ListingMeasurementOut],
    operation_id="listRentalListingMeasurements",
)
def list_rental_listing_measurements(listing_id: uuid.UUID, db: Db):
    repository = DashboardRepository(db)
    if repository.rental_listing(listing_id) is None:
        raise HTTPException(404, "Rental listing not found")
    return repository.rental_listing_measurements(listing_id)


@router.get(
    "/measurements/lead-time",
    response_model=LeadTimeSummaryOut,
    operation_id="getLeadTimeSummary",
)
def get_lead_time_summary(
    db: Db,
    source_key: str | None = None,
    classification_tag: str | None = None,
    listing_status: Literal["ACTIVE", "REMOVAL_CANDIDATE", "REMOVED"] | None = "ACTIVE",
):
    population = DashboardRepository(db).lead_time_population(
        source_key=source_key,
        classification_tag=classification_tag,
        listing_status=listing_status,
    )
    measurements = [measurement for _, measurement in population if measurement is not None]
    values = sorted(
        measurement.value
        for measurement in measurements
        if measurement.status == "MEASURED" and measurement.value is not None
    )
    middle = len(values) // 2
    median = (
        None
        if not values
        else values[middle]
        if len(values) % 2
        else (values[middle - 1] + values[middle]) / 2
    )
    return LeadTimeSummaryOut(
        source_key=source_key,
        classification_tag=classification_tag,
        listing_status=listing_status,
        rule_version="lead-time-v1",
        generated_at=datetime.now(UTC),
        population_count=len(population),
        measurement_count=len(measurements),
        measured_count=sum(item.status == "MEASURED" for item in measurements),
        missing_input_count=sum(item.status == "MISSING_INPUT" for item in measurements),
        invalid_input_count=sum(item.status == "INVALID_INPUT" for item in measurements),
        late_count=sum(item.value is not None and item.value < 0 for item in measurements),
        min_days=min(values) if values else None,
        median_days=median,
        max_days=max(values) if values else None,
    )
