from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    changes,
    controls,
    dashboard,
    documents,
    eval as eval_api,
    gaps,
    graph,
    health,
    mappings,
    obligations,
    pipeline,
    remediations,
)

# Mounted under /api/v1 by the application factory.
api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(obligations.router)
api_v1_router.include_router(controls.router)
api_v1_router.include_router(mappings.router)
api_v1_router.include_router(gaps.router)
api_v1_router.include_router(remediations.router)
api_v1_router.include_router(changes.router)
api_v1_router.include_router(pipeline.router)
api_v1_router.include_router(graph.router)
api_v1_router.include_router(eval_api.router)
api_v1_router.include_router(audit.router)
