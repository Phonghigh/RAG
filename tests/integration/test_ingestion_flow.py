"""Integration tests for ingestion flow."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from apps.shared.db import Base
from apps.ingestion.processors.github_events import GitHubEventProcessor
from tests.fixtures.github_events import PULL_REQUEST_OPENED_EVENT, PUSH_EVENT


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_process_pull_request_event(db_session: AsyncSession):
    """Test processing pull_request event."""
    # Normalize event first
    from apps.shared.utils.github_events import GitHubEventNormalizer
    
    normalized = GitHubEventNormalizer.normalize_pull_request_event(
        PULL_REQUEST_OPENED_EVENT
    )
    
    # Process event
    processor = GitHubEventProcessor(db_session)
    await processor.process_pull_request_event(normalized)
    
    # Verify PR was created
    from sqlalchemy import select
    from apps.shared.db.models import PullRequest, Repo
    
    repo = await db_session.scalar(
        select(Repo).where(Repo.name == "org/repo")
    )
    assert repo is not None
    
    pr = await db_session.scalar(
        select(PullRequest).where(
            PullRequest.repo_id == repo.id, PullRequest.number == 42
        )
    )
    assert pr is not None
    assert pr.title == "Test PR"
    assert pr.state == "open"


@pytest.mark.asyncio
async def test_process_push_event(db_session: AsyncSession):
    """Test processing push event."""
    # Normalize event first
    from apps.shared.utils.github_events import GitHubEventNormalizer
    
    normalized = GitHubEventNormalizer.normalize_push_event(PUSH_EVENT)
    
    # Process event
    processor = GitHubEventProcessor(db_session)
    await processor.process_push_event(normalized)
    
    # Verify commit was created
    from sqlalchemy import select
    from apps.shared.db.models import Commit, Repo
    
    repo = await db_session.scalar(
        select(Repo).where(Repo.name == "org/repo")
    )
    assert repo is not None
    
    commit = await db_session.scalar(
        select(Commit).where(
            Commit.repo_id == repo.id, Commit.sha == "def456"
        )
    )
    assert commit is not None
    assert commit.author == "Test User"

