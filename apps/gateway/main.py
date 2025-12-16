"""FastAPI gateway application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as loguru_logger
from apps.shared.config import settings
from apps.gateway.webhook.github import router as github_webhook_router
from apps.gateway.api.health import router as health_router
from apps.gateway.api.metrics import router as metrics_router
from apps.gateway.api.admin import router as admin_router

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper()))

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
    openapi_url="/openapi.json" if settings.app_env == "development" else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(github_webhook_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "apps.gateway.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
