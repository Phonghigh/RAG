"""Retention job worker."""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from apps.shared.db import get_async_session, Diff, TestArtifact
from apps.shared.storage import get_storage_client
from apps.shared.config import settings

logger = logging.getLogger("app.ingestion.retention")


class RetentionWorker:
    """Retention job worker to clean up old files."""
    
    def __init__(self, dry_run: bool = False):
        """Initialize retention worker.
        
        Args:
            dry_run: If True, only log what would be deleted without actually deleting
        """
        self.dry_run = dry_run
        self.storage = get_storage_client()
        self.retention_days = settings.retention_days
    
    async def run(self):
        """Run retention job."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        logger.info(
            f"Running retention job (dry_run={self.dry_run}), "
            f"cutoff_date={cutoff_date}, retention_days={self.retention_days}"
        )
        
        async for session in get_async_session():
            try:
                # Find old diffs
                old_diffs = await session.scalars(
                    select(Diff).where(Diff.created_at < cutoff_date)
                )
                diff_count = 0
                
                for diff in old_diffs:
                    if diff.object_uri:
                        await self._delete_file(diff.object_uri, "diff", diff.id)
                        diff.object_uri = None  # Clear URI but keep metadata
                        diff_count += 1
                
                # Find old test artifacts
                old_artifacts = await session.scalars(
                    select(TestArtifact).where(TestArtifact.created_at < cutoff_date)
                )
                artifact_count = 0
                
                for artifact in old_artifacts:
                    if artifact.object_uri:
                        await self._delete_file(
                            artifact.object_uri, "artifact", artifact.id
                        )
                        artifact.object_uri = None  # Clear URI but keep metadata
                        artifact_count += 1
                
                await session.commit()
                
                logger.info(
                    f"Retention job completed: "
                    f"diffs={diff_count}, artifacts={artifact_count}"
                )
                
            except Exception as e:
                logger.exception(f"Error in retention job: {e}")
                await session.rollback()
            finally:
                await session.close()
    
    async def _delete_file(self, object_uri: str, file_type: str, record_id: int):
        """Delete a file from storage.
        
        Args:
            object_uri: Object URI (e.g., s3://bucket/key or http://endpoint/bucket/key)
            file_type: Type of file (for logging)
            record_id: Database record ID (for logging)
        """
        # Parse object URI to extract bucket and key
        # Format: s3://bucket/key or http://endpoint/bucket/key
        try:
            if object_uri.startswith("s3://"):
                # s3://bucket/key
                parts = object_uri.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            elif "://" in object_uri:
                # http://endpoint/bucket/key
                parts = object_uri.split("://")[1].split("/", 2)
                bucket = parts[1] if len(parts) > 1 else settings.s3_bucket_name
                key = parts[2] if len(parts) > 2 else ""
            else:
                logger.warning(f"Unknown object URI format: {object_uri}")
                return
            
            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would delete {file_type} record_id={record_id} "
                    f"bucket={bucket} key={key}"
                )
            else:
                await self.storage.delete_file(bucket, key)
                logger.info(
                    f"Deleted {file_type} record_id={record_id} "
                    f"bucket={bucket} key={key}"
                )
        
        except Exception as e:
            logger.error(
                f"Failed to delete {file_type} record_id={record_id} "
                f"uri={object_uri}: {e}"
            )


async def main(dry_run: bool = False):
    """Main entry point for retention job."""
    worker = RetentionWorker(dry_run=dry_run)
    await worker.run()


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))

