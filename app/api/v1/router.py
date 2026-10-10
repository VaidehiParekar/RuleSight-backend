from fastapi import APIRouter

from app.api.v1 import health

# Mounted under /api/v1 by the application factory. Add feature routers here as they are built.
api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
