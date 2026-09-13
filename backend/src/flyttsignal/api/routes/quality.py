from fastapi import APIRouter, HTTPException

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.quality import QualitySummaryOut
from flyttsignal.db.repositories.quality import QualityRepository
from flyttsignal.quality.service import build_quality_summary

router = APIRouter()


@router.get(
    "/quality/summary",
    response_model=QualitySummaryOut,
    operation_id="getQualitySummary",
)
def get_quality_summary(db: Db, city_id: int = 1):
    dataset = QualityRepository(db).dataset(city_id)
    if dataset is None:
        raise HTTPException(404, "City not found")
    return build_quality_summary(dataset)
