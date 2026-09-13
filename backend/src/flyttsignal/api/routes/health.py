from fastapi import APIRouter

router = APIRouter()


@router.get("/health", operation_id="checkHealth")
def check_health() -> dict[str, str]:
    return {"status": "ok"}
