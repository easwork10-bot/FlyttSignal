from typing import Annotated

from fastapi import APIRouter, Query

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.spatial_features import spatial_feature_out
from flyttsignal.api.schemas.spatial_features import SpatialFeatureList
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/spatial-features",
    response_model=SpatialFeatureList,
    operation_id="listSpatialFeatures",
)
def list_spatial_features(db: Db, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    found = DashboardRepository(db).spatial_features(limit)
    return SpatialFeatureList(
        items=[spatial_feature_out(item, geometry) for item, geometry in found],
        count=len(found),
    )
