from fastapi import APIRouter

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.cities import CityOut
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get("/cities", response_model=list[CityOut], operation_id="listCities")
def list_cities(db: Db):
    return DashboardRepository(db).cities()
