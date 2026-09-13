import uuid

from fastapi import APIRouter, HTTPException

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.properties import property_out
from flyttsignal.api.schemas.properties import PropertyOut
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/properties/{property_id}",
    response_model=PropertyOut,
    operation_id="getProperty",
)
def get_property(property_id: uuid.UUID, db: Db):
    found = DashboardRepository(db).property(property_id)
    if found is None:
        raise HTTPException(404, "Property not found")
    return property_out(found)
