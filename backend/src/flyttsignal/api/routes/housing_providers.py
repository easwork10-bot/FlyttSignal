from fastapi import APIRouter

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.housing_providers import housing_provider_out
from flyttsignal.api.schemas.housing_providers import HousingProviderList
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/housing-providers",
    response_model=HousingProviderList,
    operation_id="listHousingProviders",
)
def list_housing_providers(db: Db, city_id: int = 1):
    found = DashboardRepository(db).housing_providers(city_id)
    return HousingProviderList(
        items=[housing_provider_out(item, city_id) for item in found], count=len(found)
    )
