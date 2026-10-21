from fastapi import APIRouter

from app.api.routes import auth, health, meta

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(auth.router)
