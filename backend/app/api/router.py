from fastapi import APIRouter

from app.api.routes import auth, calendar, health, integrations, meta, task_blocks, tasks, time_entries, timer

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(timer.router)
api_router.include_router(time_entries.router)
api_router.include_router(integrations.router)
api_router.include_router(calendar.router)
api_router.include_router(task_blocks.router)
