from fastapi import APIRouter

from flyttsignal.api.dependencies import Db
from flyttsignal.api.schemas.sources import SourceOut
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get("/sources", response_model=list[SourceOut], operation_id="listSources")
def list_sources(db: Db):
    return DashboardRepository(db).sources()
