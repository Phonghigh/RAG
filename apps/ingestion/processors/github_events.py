"""GitHub event processors."""
import logging
from typing import Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.shared.db.models import (
    Repo,
    Commit,
    PullRequest,
    Diff,
    TestArtifact,
    Notification,
)
from apps.shared.storage import get_storage_client
from apps.shared.config import settings

logger = logging.getLogger("app.ingestion.processors")


class GitHubEventProcessor:
    """Process normalized GitHub events."""
    
    def __init__(self, session: AsyncSession):
        """Initialize processor with database session."""
        self.session = session
        self.storage = get_storage_client()
    
    async def process_push_event(self, event: dict[str, Any]) -> None:
        """Process push event."""
        repo_info = event.get("repo", {})
        repo_name = repo_info.get("name")
        if not repo_name:
            logger.warning("Push event missing repo name")
            return
        
        # Get or create repo
        repo = await self._get_or_create_repo(repo_name, repo_info)
        
        # Process commits
        commits_data = event.get("commits", [])
        for commit_data in commits_data:
            await self._process_commit(repo.id, commit_data, event)
        
        await self.session.commit()
        logger.info(f"Processed push event for repo={repo_name}, commits={len(commits_data)}")
    
    async def process_pull_request_event(self, event: dict[str, Any]) -> None:
        """Process pull_request event."""
        repo_info = event.get("repo", {})
        pr_info = event.get("pull_request", {})
        action = event.get("action")
        
        repo_name = repo_info.get("name")
        if not repo_name:
            logger.warning("PR event missing repo name")
            return
        
        # Get or create repo
        repo = await self._get_or_create_repo(repo_name, repo_info)
        
        # Get or create PR
        pr_number = pr_info.get("number")
        pr = await self._get_or_create_pr(repo.id, pr_number, pr_info)
        
        # Update PR state if needed
        if action in ["opened", "synchronize", "closed"]:
            pr.state = pr_info.get("state")
            pr.updated_at = datetime.utcnow()
        
        await self.session.commit()
        logger.info(f"Processed PR event action={action} repo={repo_name} number={pr_number}")
    
    async def process_check_run_event(self, event: dict[str, Any]) -> None:
        """Process check_run event."""
        repo_info = event.get("repo", {})
        check_run_info = event.get("check_run", {})
        action = event.get("action")
        
        repo_name = repo_info.get("name")
        if not repo_name:
            logger.warning("Check run event missing repo name")
            return
        
        # Get or create repo
        repo = await self._get_or_create_repo(repo_name, repo_info)
        
        # Find PR by head_sha
        head_sha = check_run_info.get("head_sha")
        if head_sha:
            pr = await self.session.scalar(
                select(PullRequest).where(
                    PullRequest.repo_id == repo.id,
                    PullRequest.head_sha == head_sha,
                )
            )
            
            if pr and action == "completed":
                # Store test artifact metadata
                # Note: Actual artifact download would happen separately
                artifact = TestArtifact(
                    pr_id=pr.id,
                    framework=check_run_info.get("name", "unknown"),
                    conclusion=check_run_info.get("conclusion"),
                    html_url=check_run_info.get("html_url"),
                )
                self.session.add(artifact)
                await self.session.flush()
        
        await self.session.commit()
        logger.info(f"Processed check_run event action={action} repo={repo_name}")
    
    async def _get_or_create_repo(
        self, repo_name: str, repo_info: dict[str, Any]
    ) -> Repo:
        """Get or create repository."""
        repo = await self.session.scalar(
            select(Repo).where(Repo.name == repo_name)
        )
        
        if not repo:
            repo = Repo(
                name=repo_name,
                monorepo=True,  # Default, can be updated via service map
            )
            self.session.add(repo)
            await self.session.flush()
        
        return repo
    
    async def _get_or_create_pr(
        self, repo_id: int, pr_number: int, pr_info: dict[str, Any]
    ) -> PullRequest:
        """Get or create pull request."""
        pr = await self.session.scalar(
            select(PullRequest).where(
                PullRequest.repo_id == repo_id,
                PullRequest.number == pr_number,
            )
        )
        
        if not pr:
            pr = PullRequest(
                repo_id=repo_id,
                number=pr_number,
                title=pr_info.get("title"),
                author=pr_info.get("author"),
                created_at=pr_info.get("created_at"),
                merged_at=pr_info.get("merged_at"),
                state=pr_info.get("state"),
                base_branch=pr_info.get("base_branch"),
                head_sha=pr_info.get("head_sha"),
            )
            self.session.add(pr)
            await self.session.flush()
        
        return pr
    
    async def _process_commit(
        self, repo_id: int, commit_data: dict[str, Any], event: dict[str, Any]
    ) -> None:
        """Process a single commit."""
        sha = commit_data.get("sha")
        if not sha:
            return
        
        # Check if commit already exists
        existing = await self.session.scalar(
            select(Commit).where(Commit.repo_id == repo_id, Commit.sha == sha)
        )
        if existing:
            return
        
        # Calculate LOC changes
        added_files = commit_data.get("added", [])
        removed_files = commit_data.get("removed", [])
        modified_files = commit_data.get("modified", [])
        
        commit = Commit(
            repo_id=repo_id,
            sha=sha,
            author=commit_data.get("author"),
            authored_at=commit_data.get("authored_at"),
            files_changed=len(set(added_files + removed_files + modified_files)),
            # LOC would be calculated from actual diff parsing
        )
        self.session.add(commit)
        await self.session.flush()
        
        # Store diff metadata (actual diff storage happens separately)
        # This is a placeholder for diff processing

