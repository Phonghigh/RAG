"""Artifact storage operations."""
import logging
from io import BytesIO
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from apps.shared.storage import get_storage_client
from apps.shared.db.models import TestArtifact
from apps.shared.config import settings

logger = logging.getLogger("app.ingestion.storage.artifact")


async def store_test_artifact(
    session: AsyncSession,
    pr_id: Optional[int],
    commit_id: Optional[int],
    framework: str,
    artifact_content: bytes,
    content_type: str = "application/xml",
    passed: Optional[int] = None,
    failed: Optional[int] = None,
    skipped: Optional[int] = None,
    coverage_line: Optional[float] = None,
    coverage_branch: Optional[float] = None,
) -> TestArtifact:
    """Store a test artifact in S3 and create database record."""
    storage = get_storage_client()
    
    # Generate object key
    key_parts = ["artifacts"]
    if pr_id:
        key_parts.append(f"pr-{pr_id}")
    if commit_id:
        key_parts.append(f"commit-{commit_id}")
    key_parts.append(f"{framework}.xml")
    object_key = "/".join(key_parts)
    
    # Upload to storage
    file_obj = BytesIO(artifact_content)
    object_uri = await storage.upload_file(
        bucket=settings.s3_bucket_name,
        key=object_key,
        file_obj=file_obj,
        content_type=content_type,
    )
    
    # Create database record
    artifact = TestArtifact(
        pr_id=pr_id,
        commit_id=commit_id,
        framework=framework,
        passed=passed,
        failed=failed,
        skipped=skipped,
        coverage_line=coverage_line,
        coverage_branch=coverage_branch,
        object_uri=object_uri,
    )
    session.add(artifact)
    await session.flush()
    
    logger.info(
        f"Stored artifact pr_id={pr_id} commit_id={commit_id} "
        f"framework={framework} object_uri={object_uri}"
    )
    return artifact

