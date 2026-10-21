from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Liveness probe")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
