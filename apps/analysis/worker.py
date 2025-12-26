"""Analysis worker main loop."""
import asyncio
import logging
import json
from typing import Callable, Optional
from urllib.parse import urlparse
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.shared.db import get_async_session
from apps.shared.db.models import Finding, Repo, PullRequest, Diff
from apps.shared.mq import get_mq_client, MQClient
from apps.shared.storage import get_storage_client
from apps.analysis.processors.pr_analyzer import PRAnalyzer
from apps.shared.config import settings

logger = logging.getLogger("app.analysis.worker")


class AnalysisWorker:
    """Main analysis worker."""
    
    def __init__(self, rules_config_path: str = None):
        """Initialize analysis worker."""
        self.mq_client: MQClient = get_mq_client()
        self.storage = get_storage_client()
        self.pr_analyzer = PRAnalyzer(rules_config_path)
        self.running = False
    
    async def start(self):
        """Start the worker."""
        logger.info("Starting analysis worker...")
        self.running = True
        
        # Subscribe to PR events (analysis happens after ingestion)
        topics = [
            "github.pull_request",
        ]
        
        for topic in topics:
            await self.mq_client.subscribe(
                topic,
                self._handle_message,
                group_id="analysis-worker",
            )
        
        logger.info("Analysis worker started, subscribed to topics: %s", topics)
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the worker."""
        logger.info("Stopping analysis worker...")
        self.running = False
        await self.mq_client.close()
        logger.info("Analysis worker stopped")
    
    async def _handle_message(self, message: dict):
        """Handle a message from the queue."""
        event_type = message.get("event_type")
        action = message.get("action")
        
        # Only analyze opened or synchronized PRs
        if event_type != "pull_request" or action not in ["opened", "synchronize"]:
            return
        
        logger.info(f"Processing analysis for PR event type={event_type}, action={action}")
        
        async for session in get_async_session():
            try:
                await self._analyze_pr(session, message)
            except Exception as e:
                logger.exception(f"Error processing analysis: {e}")
                await session.rollback()
            finally:
                await session.close()
    
    async def _analyze_pr(self, session: AsyncSession, event: dict):
        """
        Analyze a pull request.
        
        Handles errors gracefully, allowing partial success if some files fail.
        """
        pr_info = event.get("pull_request", {})
        repo_info = event.get("repo", {})
        
        repo_name = repo_info.get("name")
        pr_number = pr_info.get("number")
        
        if not repo_name or not pr_number:
            logger.warning("PR event missing repo name or PR number")
            return
        
        analysis_start_time = asyncio.get_event_loop().time()
        
        try:
            # Get repo and PR from database
            from sqlalchemy import select
            repo = await session.scalar(
                select(Repo).where(Repo.name == repo_name)
            )
            if not repo:
                logger.warning(f"Repo not found: {repo_name}")
                return
            
            pr = await session.scalar(
                select(PullRequest).where(
                    PullRequest.repo_id == repo.id,
                    PullRequest.number == pr_number,
                )
            )
            if not pr:
                logger.warning(f"PR not found: {repo_name}#{pr_number}")
                return
            
            # Get service map
            service_map = repo.service_map or {}
            
            # Fetch diffs from storage with retry logic for transient errors
            diffs = await self._get_pr_diffs_with_retry(pr, repo, session, max_retries=3)
            
            if not diffs:
                logger.warning(f"No diffs found for PR {repo_name}#{pr_number}")
                return
            
            logger.info(
                f"Starting analysis for PR {repo_name}#{pr_number}: "
                f"{len(diffs)} files to analyze"
            )
            
            # Run analysis
            pr_data = {
                'number': pr_number,
                'repo': repo_name,
            }
            
            try:
                analysis_results = self.pr_analyzer.analyze_pr(
                    pr_data=pr_data,
                    diffs=diffs,
                    service_map=service_map,
                )
            except Exception as e:
                logger.exception(f"Error during PR analysis for {repo_name}#{pr_number}: {e}")
                # Store error as a finding for visibility
                error_finding = Finding(
                    repo_id=repo.id,
                    pr_id=pr.id,
                    file_path=None,
                    rule_id="analysis_error",
                    severity="error",
                    message=f"Analysis failed: {str(e)}",
                    details={"error_type": type(e).__name__},
                )
                session.add(error_finding)
                await session.commit()
                return
            
            # Store findings in database
            findings_added = 0
            for finding_data in analysis_results.get('findings', []):
                try:
                    finding = Finding(
                        repo_id=repo.id,
                        pr_id=pr.id,
                        file_path=finding_data.get('file_path'),
                        rule_id=finding_data.get('rule_id'),
                        severity=finding_data.get('severity', 'medium'),
                        message=finding_data.get('message'),
                        details=finding_data.get('details', {}),
                        owner_hint=self._extract_owner_hint(
                            finding_data.get('file_path'),
                            analysis_results.get('ownership', {})
                        ),
                    )
                    session.add(finding)
                    findings_added += 1
                except Exception as e:
                    logger.exception(f"Error storing finding: {e}")
                    # Continue with other findings
            
            await session.commit()
            
            analysis_duration = asyncio.get_event_loop().time() - analysis_start_time
            findings_count = len(analysis_results.get('findings', []))
            files_analyzed = analysis_results.get('files_analyzed', 0)
            
            logger.info(
                f"Analysis complete for PR {repo_name}#{pr_number}: "
                f"{findings_count} findings, {files_analyzed} files analyzed, "
                f"{findings_added} findings stored, duration={analysis_duration:.2f}s"
            )
            
            # Trigger indexing after successful analysis
            if getattr(settings, 'indexing_enabled', True):
                try:
                    await self._trigger_indexing(session, repo.id, pr.id, pr_number)
                except Exception as e:
                    # Don't fail analysis if indexing trigger fails
                    logger.exception(f"Error triggering indexing for PR {pr_number}: {e}")
        
        except Exception as e:
            logger.exception(f"Unexpected error analyzing PR {repo_name}#{pr_number}: {e}")
            await session.rollback()
            raise
    
    async def _get_pr_diffs_with_retry(
        self,
        pr,
        repo,
        session: AsyncSession,
        max_retries: int = 3
    ) -> list[dict]:
        """
        Get PR diffs with retry logic for transient storage errors.
        
        Args:
            pr: PullRequest model instance
            repo: Repo model instance
            session: Database session
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of diff dicts
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                diffs = await self._get_pr_diffs(pr, repo, session)
                return diffs
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Error fetching diffs for PR {pr.id} (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to fetch diffs for PR {pr.id} after {max_retries} attempts: {e}")
        
        # If all retries failed, return empty list (partial failure)
        return []
    
    async def _get_pr_diffs(self, pr, repo, session: AsyncSession) -> list[dict]:
        """
        Get PR diffs from storage.
        
        Args:
            pr: PullRequest model instance
            repo: Repo model instance
            session: Database session
            
        Returns:
            List of diff dicts with 'path', 'content', 'language' keys
        """
        diffs_list = []
        
        # Query all diffs for this PR
        diff_records = await session.scalars(
            select(Diff).where(Diff.pr_id == pr.id)
        )
        diff_records = list(diff_records)
        
        if not diff_records:
            logger.debug(f"No diff records found for PR {pr.id}")
            return diffs_list
        
        logger.info(f"Found {len(diff_records)} diff records for PR {pr.id}")
        
        # Process each diff
        for diff_record in diff_records:
            try:
                if not diff_record.object_uri:
                    logger.warning(f"Diff {diff_record.id} has no object_uri, skipping")
                    continue
                
                # Parse object_uri to extract bucket and key
                # Format can be: http://endpoint/bucket/key or s3://bucket/key
                object_uri = diff_record.object_uri
                parsed_uri = urlparse(object_uri)
                
                bucket = None
                key = None
                
                if parsed_uri.scheme == 's3':
                    # s3://bucket/key format
                    bucket = parsed_uri.netloc
                    key = parsed_uri.path.lstrip('/')
                elif parsed_uri.scheme in ('http', 'https'):
                    # http://endpoint/bucket/key format
                    path_parts = parsed_uri.path.strip('/').split('/', 1)
                    if len(path_parts) == 2:
                        bucket, key = path_parts
                    else:
                        logger.warning(f"Invalid object_uri format: {object_uri}")
                        continue
                else:
                    logger.warning(f"Unknown URI scheme in object_uri: {object_uri}")
                    continue
                
                if not bucket or not key:
                    logger.warning(f"Could not extract bucket/key from object_uri: {object_uri}")
                    continue
                
                # Download diff content from storage
                try:
                    diff_content_bytes = await self.storage.download_file(bucket, key)
                    diff_content = diff_content_bytes.decode('utf-8')
                except Exception as e:
                    logger.exception(f"Error downloading diff {diff_record.id} from storage: {e}")
                    continue
                
                if not diff_content:
                    logger.warning(f"Empty diff content for diff {diff_record.id}")
                    continue
                
                # Determine language from diff record or file path
                language = diff_record.lang
                if not language and diff_record.path:
                    # Fallback to file extension detection
                    ext = Path(diff_record.path).suffix.lower()
                    language_map = {
                        '.py': 'python',
                    }
                    language = language_map.get(ext)
                
                # Add to results
                diffs_list.append({
                    'path': diff_record.path or '',
                    'content': diff_content,
                    'language': language,
                })
                
            except Exception as e:
                logger.exception(f"Error processing diff {diff_record.id}: {e}")
                # Continue with other diffs even if one fails
                continue
        
        logger.info(f"Successfully fetched {len(diffs_list)} diffs for PR {pr.id}")
        return diffs_list
    
    async def _trigger_indexing(self, session: AsyncSession, repo_id: int, pr_id: int, pr_number: int):
        """
        Trigger indexing for analyzed PR diffs.
        
        Args:
            session: Database session
            repo_id: Repository ID
            pr_id: Pull Request ID
            pr_number: Pull Request number
        """
        try:
            # Get diff IDs for this PR
            diff_records = await session.scalars(
                select(Diff.id).where(Diff.pr_id == pr_id)
            )
            diff_ids = [diff_id for diff_id in diff_records]
            
            if not diff_ids:
                logger.debug(f"No diffs to index for PR {pr_id}")
                return
            
            # Publish indexing request message
            indexing_message = {
                'event_type': 'indexing.requested',
                'repo_id': repo_id,
                'pr_id': pr_id,
                'pr_number': pr_number,
                'diff_ids': diff_ids,
            }
            
            await self.mq_client.publish('indexing.requested', indexing_message)
            logger.info(f"Published indexing request for PR {pr_number} with {len(diff_ids)} diffs")
            
        except Exception as e:
            # Don't fail analysis if indexing trigger fails
            logger.exception(f"Error triggering indexing for PR {pr_id}: {e}")
    
    def _extract_owner_hint(self, file_path: str, ownership: dict) -> Optional[str]:
        """Extract owner hint from ownership results."""
        if file_path in ownership:
            candidates = ownership[file_path]
            if candidates:
                top_candidate = candidates[0]
                return f"{top_candidate['candidate']} ({top_candidate['score']:.0%})"
        return None


async def main():
    """Main entry point."""
    rules_config_path = getattr(settings, 'rules_config_path', None)
    worker = AnalysisWorker(rules_config_path)
    await worker.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
