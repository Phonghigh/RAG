"""Integration tests for analysis flow."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from apps.shared.db import Base
from apps.analysis.processors.code_analyzer import CodeAnalyzer
from apps.analysis.processors.pr_analyzer import PRAnalyzer


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


@pytest.mark.asyncio
async def test_code_analyzer_flow(db_session: AsyncSession):
    """Test code analyzer flow."""
    analyzer = CodeAnalyzer()
    
    code = """def test_function():
    api_key = "sk_live_1234567890"
    return api_key"""
    
    result = analyzer.analyze_file(code, "app.py", "python")
    
    assert result['path'] == "app.py"
    assert result['parsed'] is not None
    # Should detect secret
    assert len(result['secrets']) > 0


@pytest.mark.asyncio
async def test_pr_analyzer_flow(db_session: AsyncSession):
    """Test PR analyzer flow."""
    analyzer = PRAnalyzer()
    
    pr_data = {
        'number': 1,
        'repo': 'test/repo',
    }
    
    diffs = [
        {
            'path': 'test.py',
            'content': 'def test(): pass',
            'language': 'python',
        }
    ]
    
    result = analyzer.analyze_pr(pr_data, diffs)
    
    assert result['pr_id'] == 1
    assert result['files_analyzed'] > 0
