"""Diff storage operations."""
import logging
from io import BytesIO
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from apps.shared.storage import get_storage_client
from apps.shared.db.models import Diff
from apps.shared.config import settings

logger = logging.getLogger("app.ingestion.storage.diff")


async def store_diff(
    session: AsyncSession,
    repo_id: int,
    pr_id: Optional[int],
    commit_id: Optional[int],
    path: str,
    diff_content: str,
    lang: Optional[str] = None,
    added_loc: Optional[int] = None,
    removed_loc: Optional[int] = None,
    hunk_count: Optional[int] = None,
) -> Diff:
    """Store a diff file in S3 and create database record."""
    storage = get_storage_client()
    
    # Generate object key
    key_parts = [str(repo_id)]
    if pr_id:
        key_parts.append(f"pr-{pr_id}")
    if commit_id:
        key_parts.append(f"commit-{commit_id}")
    key_parts.append(path.replace("/", "_"))
    object_key = "/".join(key_parts)
    
    # Upload to storage
    file_obj = BytesIO(diff_content.encode("utf-8"))
    object_uri = await storage.upload_file(
        bucket=settings.s3_bucket_name,
        key=object_key,
        file_obj=file_obj,
        content_type="text/plain",
    )
    
    # Create database record
    diff = Diff(
        repo_id=repo_id,
        pr_id=pr_id,
        commit_id=commit_id,
        path=path,
        lang=lang,
        added_loc=added_loc,
        removed_loc=removed_loc,
        hunk_count=hunk_count,
        object_uri=object_uri,
    )
    session.add(diff)
    await session.flush()
    
    logger.info(f"Stored diff repo_id={repo_id} path={path} object_uri={object_uri}")
    return diff

