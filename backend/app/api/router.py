from fastapi import APIRouter

from app.api.routes import auth, finance, health, meta, tasks, time_entries, timer

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(timer.router)
api_router.include_router(time_entries.router)
api_router.include_router(finance.router)
