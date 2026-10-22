from fastapi import APIRouter

from app.api.routes import (
    academic,
    analytics,
    auth,
    health,
    github,
    integrations,
    meta,
    planning,
    tasks,
    timer,
    telegram,
    tutoring,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(github.router)
api_router.include_router(telegram.router)
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(timer.router)
api_router.include_router(integrations.router)
api_router.include_router(planning.router)
api_router.include_router(tutoring.router)
api_router.include_router(academic.router)
api_router.include_router(analytics.router)
