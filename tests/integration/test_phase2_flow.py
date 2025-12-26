"""Integration tests for Phase 2: Analysis → Indexing → RAG Query flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from apps.shared.db import Base
from apps.shared.db.models import Repo, PullRequest, Diff, Finding, RagChunk
from apps.analysis.worker import AnalysisWorker
from apps.indexer.worker import IndexerWorker
from apps.rag.retriever import HybridRetriever
from apps.indexer.embedder import Embedder


@pytest.fixture
async def db_session():
    """Create test database session."""
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


@pytest.fixture
def mock_storage():
    """Mock storage client."""
    storage = AsyncMock()
    storage.download_file = AsyncMock(return_value=b"def test_function():\n    return 'test'")
    return storage


@pytest.fixture
def mock_mq_client():
    """Mock message queue client."""
    mq_client = AsyncMock()
    mq_client.publish = AsyncMock()
    mq_client.subscribe = AsyncMock()
    mq_client.close = AsyncMock()
    return mq_client


@pytest.fixture
async def test_repo_and_pr(db_session: AsyncSession):
    """Create test repo and PR."""
    repo = Repo(
        name="test/repo",
        monorepo=True,
        service_map={},
    )
    db_session.add(repo)
    await db_session.flush()
    
    pr = PullRequest(
        repo_id=repo.id,
        number=1,
        title="Test PR",
        author="testuser",
        state="open",
        base_branch="main",
        head_sha="abc123def456",
    )
    db_session.add(pr)
    await db_session.flush()
    
    # Create a diff record
    diff = Diff(
        repo_id=repo.id,
        pr_id=pr.id,
        path="app.py",
        lang="python",
        added_loc=10,
        removed_loc=2,
        object_uri="http://localhost:9000/test-bucket/repo-1/pr-1/test.py",
    )
    db_session.add(diff)
    await db_session.commit()
    
    return repo, pr, diff


@pytest.mark.asyncio
async def test_analysis_worker_fetches_diffs(
    db_session: AsyncSession,
    mock_storage,
    mock_mq_client,
    test_repo_and_pr,
):
    """Test that analysis worker can fetch diffs from storage."""
    repo, pr, diff = test_repo_and_pr
    
    # Create analysis worker with mocked dependencies
    with patch('apps.analysis.worker.get_storage_client', return_value=mock_storage):
        with patch('apps.analysis.worker.get_mq_client', return_value=mock_mq_client):
            worker = AnalysisWorker()
            
            # Test _get_pr_diffs method
            diffs = await worker._get_pr_diffs(pr, repo, db_session)
            
            assert len(diffs) == 1
            assert diffs[0]['path'] == "app.py"
            assert diffs[0]['language'] == "python"
            assert 'content' in diffs[0]
            
            # Verify storage was called
            mock_storage.download_file.assert_called_once()


@pytest.mark.asyncio
async def test_analysis_worker_stores_findings(
    db_session: AsyncSession,
    mock_storage,
    mock_mq_client,
    test_repo_and_pr,
):
    """Test that analysis worker stores findings in database."""
    repo, pr, diff = test_repo_and_pr
    
    # Mock storage to return code with a secret
    mock_storage.download_file = AsyncMock(
        return_value=b"api_key = 'sk_live_1234567890abcdef'"
    )
    
    with patch('apps.analysis.worker.get_storage_client', return_value=mock_storage):
        with patch('apps.analysis.worker.get_mq_client', return_value=mock_mq_client):
            worker = AnalysisWorker()
            
            # Create a mock event
            event = {
                'event_type': 'pull_request',
                'action': 'opened',
                'pull_request': {'number': 1},
                'repo': {'name': 'test/repo'},
            }
            
            # Run analysis
            await worker._analyze_pr(db_session, event)
            
            # Verify findings were stored
            findings = await db_session.scalars(
                select(Finding).where(Finding.pr_id == pr.id)
            )
            findings_list = list(findings)
            
            # Should have at least one finding (secret detected)
            assert len(findings_list) > 0
            
            # Verify indexing was triggered
            mock_mq_client.publish.assert_called_once()
            call_args = mock_mq_client.publish.call_args
            assert call_args[0][0] == 'indexing.requested'
            assert 'diff_ids' in call_args[0][1]


@pytest.mark.asyncio
async def test_indexer_worker_indexes_diffs(
    db_session: AsyncSession,
    mock_storage,
    test_repo_and_pr,
):
    """Test that indexer worker can index diffs."""
    repo, pr, diff = test_repo_and_pr
    
    # Mock embedder to return simple embeddings
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[[0.1] * 384])  # 384-dim embedding
    
    with patch('apps.indexer.worker.get_storage_client', return_value=mock_storage):
        with patch('apps.indexer.worker.Embedder', return_value=mock_embedder):
            worker = IndexerWorker()
            
            # Index the diff
            chunks_indexed = await worker.index_diff(diff, db_session)
            
            # Should have indexed at least one chunk
            assert chunks_indexed > 0
            
            # Verify chunks were stored in database
            chunks = await db_session.scalars(
                select(RagChunk).where(RagChunk.repo_id == repo.id)
            )
            chunks_list = list(chunks)
            assert len(chunks_list) > 0
            
            # Verify chunk has required fields
            chunk = chunks_list[0]
            assert chunk.content is not None
            assert chunk.embedding is not None
            assert chunk.path == "app.py"


@pytest.mark.asyncio
async def test_indexer_worker_handles_indexing_message(
    db_session: AsyncSession,
    mock_storage,
    test_repo_and_pr,
):
    """Test that indexer worker can handle indexing request messages."""
    repo, pr, diff = test_repo_and_pr
    
    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[[0.1] * 384])
    
    # Create indexing message
    indexing_message = {
        'event_type': 'indexing.requested',
        'repo_id': repo.id,
        'pr_id': pr.id,
        'pr_number': pr.number,
        'diff_ids': [diff.id],
    }
    
    async def mock_get_async_session():
        """Mock async session generator that yields test session."""
        yield db_session
    
    with patch('apps.indexer.worker.get_storage_client', return_value=mock_storage):
        with patch('apps.indexer.worker.Embedder', return_value=mock_embedder):
            with patch('apps.indexer.worker.get_async_session', side_effect=mock_get_async_session):
                worker = IndexerWorker()
                
                # Handle the message
                await worker._handle_indexing_message(indexing_message)
                
                # Verify chunks were indexed
                await db_session.commit()
                chunks = await db_session.scalars(
                    select(RagChunk).where(RagChunk.repo_id == repo.id)
                )
                chunks_list = list(chunks)
                assert len(chunks_list) > 0


@pytest.mark.asyncio
async def test_rag_query_retrieves_indexed_chunks(
    db_session: AsyncSession,
    test_repo_and_pr,
):
    """Test that RAG query can retrieve indexed chunks."""
    repo, pr, diff = test_repo_and_pr
    
    # Create a mock chunk in the database
    mock_embedding = [0.1] * 384
    
    chunk = RagChunk(
        repo_id=repo.id,
        source_type='diff',
        source_id=str(diff.id),
        path="test.py",
        lang="python",
        content="def test_function():\n    return 'test'",
        ast_signature="test_function",
        embedding=mock_embedding,
    )
    db_session.add(chunk)
    await db_session.commit()
    
    # Create retriever
    mock_embedder = MagicMock()
    mock_embedder.embed_single = MagicMock(return_value=mock_embedding)
    
    retriever = HybridRetriever(db_session, mock_embedder)
    
    # Query
    results = await retriever.retrieve(
        query="test function",
        repo_id=repo.id,
        top_k=5,
    )
    
    # Should retrieve the chunk
    assert len(results) > 0
    assert results[0]['content'] == "def test_function():\n    return 'test'"
    assert results[0]['path'] == "test.py"


@pytest.mark.asyncio
async def test_end_to_end_flow(
    db_session: AsyncSession,
    mock_storage,
    mock_mq_client,
    test_repo_and_pr,
):
    """Test end-to-end flow: analysis → indexing → RAG query."""
    repo, pr, diff = test_repo_and_pr
    
    # Mock embedder
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[[0.1] * 384])
    mock_embedder.embed_single = MagicMock(return_value=[0.1] * 384)
    
    # Step 1: Analysis
    mock_storage.download_file = AsyncMock(
        return_value=b"def calculate_total(items):\n    return sum(items)"
    )
    
    with patch('apps.analysis.worker.get_storage_client', return_value=mock_storage):
        with patch('apps.analysis.worker.get_mq_client', return_value=mock_mq_client):
            analysis_worker = AnalysisWorker()
            
            event = {
                'event_type': 'pull_request',
                'action': 'opened',
                'pull_request': {'number': 1},
                'repo': {'name': 'test/repo'},
            }
            
            await analysis_worker._analyze_pr(db_session, event)
            
            # Verify findings stored
            findings = await db_session.scalars(
                select(Finding).where(Finding.pr_id == pr.id)
            )
            assert len(list(findings)) >= 0  # May or may not have findings
    
    # Step 2: Indexing (triggered by message)
    indexing_message = {
        'event_type': 'indexing.requested',
        'repo_id': repo.id,
        'pr_id': pr.id,
        'pr_number': pr.number,
        'diff_ids': [diff.id],
    }
    
    async def mock_get_async_session():
        """Mock async session generator that yields test session."""
        yield db_session
    
    with patch('apps.indexer.worker.get_storage_client', return_value=mock_storage):
        with patch('apps.indexer.worker.Embedder', return_value=mock_embedder):
            with patch('apps.indexer.worker.get_async_session', side_effect=mock_get_async_session):
                indexer_worker = IndexerWorker()
                await indexer_worker._handle_indexing_message(indexing_message)
                
                # Verify chunks indexed
                await db_session.commit()
                chunks = await db_session.scalars(
                    select(RagChunk).where(RagChunk.repo_id == repo.id)
                )
                assert len(list(chunks)) > 0
    
    # Step 3: RAG Query
    retriever = HybridRetriever(db_session, mock_embedder)
    results = await retriever.retrieve(
        query="calculate total",
        repo_id=repo.id,
        top_k=5,
    )
    
    # Should retrieve relevant chunks
    assert len(results) > 0

