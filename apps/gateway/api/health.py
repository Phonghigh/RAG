"""Health check endpoints."""
from fastapi import APIRouter
from apps.shared.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check."""
    return {
        "status": "ok",
        "environment": settings.app_env,
        "service": settings.app_name,
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check (for Kubernetes)."""
    # TODO: Add database connectivity check
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Liveness check (for Kubernetes)."""
    return {"status": "alive"}

