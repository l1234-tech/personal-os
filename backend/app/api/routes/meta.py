from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/meta", summary="API metadata")
def api_meta() -> dict[str, str]:
    return {"name": settings.app_name, "environment": settings.app_env, "status": "foundation"}
