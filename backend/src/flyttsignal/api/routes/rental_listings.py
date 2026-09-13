import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.rental_listings import rental_listing_out
from flyttsignal.api.schemas.rental_listings import (
    RentalListingClassificationOut,
    RentalListingList,
)
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/rental-listings",
    response_model=RentalListingList,
    operation_id="listRentalListings",
)
def list_rental_listings(
    db: Db,
    status: str | None = "ACTIVE",
    provider: str | None = None,
    data_mode: Literal["fixture", "live"] | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    found = DashboardRepository(db).rental_listings(
        status=status, provider=provider, data_mode=data_mode, limit=limit
    )
    return RentalListingList(items=[rental_listing_out(item) for item in found], count=len(found))


@router.get(
    "/rental-listings/{listing_id}/classifications",
    response_model=list[RentalListingClassificationOut],
    operation_id="listRentalListingClassifications",
)
def list_rental_listing_classifications(listing_id: uuid.UUID, db: Db):
    repository = DashboardRepository(db)
    if repository.rental_listing(listing_id) is None:
        raise HTTPException(404, "Rental listing not found")
    return repository.rental_listing_classifications(listing_id)
