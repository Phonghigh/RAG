"""Admin endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from apps.shared.db import get_async_session, Repo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter(prefix="/admin", tags=["admin"])


class ServiceMapUpdate(BaseModel):
    """Service map update model."""
    repo_name: str
    service_map: dict


@router.post("/service-map")
async def update_service_map(
    update: ServiceMapUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    """Update service map for a repository."""
    # Find or create repo
    repo = await session.scalar(
        select(Repo).where(Repo.name == update.repo_name)
    )
    if not repo:
        repo = Repo(name=update.repo_name, service_map=update.service_map)
        session.add(repo)
    else:
        repo.service_map = update.service_map
    
    await session.commit()
    await session.refresh(repo)
    
    return {
        "repo_id": repo.id,
        "repo_name": repo.name,
        "service_map": repo.service_map,
    }


@router.get("/service-map/{repo_name}")
async def get_service_map(
    repo_name: str,
    session: AsyncSession = Depends(get_async_session),
):
    """Get service map for a repository."""
    repo = await session.scalar(
        Repo.__table__.select().where(Repo.name == repo_name)
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    return {
        "repo_id": repo.id,
        "repo_name": repo.name,
        "service_map": repo.service_map,
    }

