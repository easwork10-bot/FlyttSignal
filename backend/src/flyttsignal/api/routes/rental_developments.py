from fastapi import APIRouter

from flyttsignal.api.dependencies import Db
from flyttsignal.api.mappers.rental_developments import rental_project_out
from flyttsignal.api.schemas.rental_developments import RentalProjectList
from flyttsignal.db.repositories.dashboard import DashboardRepository

router = APIRouter()


@router.get(
    "/rental-projects",
    response_model=RentalProjectList,
    operation_id="listRentalProjects",
)
def list_rental_projects(db: Db, city: str = "Uppsala"):
    found = DashboardRepository(db).rental_projects(city)
    return RentalProjectList(
        items=[rental_project_out(project, count) for project, count in found],
        count=len(found),
    )
