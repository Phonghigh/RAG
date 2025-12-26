"""RAG query API endpoints."""
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.shared.db import get_async_session
from apps.shared.db.models import Repo
from apps.rag.models import RAGQuery, RAGResponse, Citation
from apps.rag.retriever import HybridRetriever
from apps.rag.generator import ResponseGenerator
from apps.indexer.embedder import Embedder
from apps.shared.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


async def get_repo_id(repo_name: str, session: AsyncSession) -> int:
    """Get repository ID by name."""
    repo = await session.scalar(
        select(Repo).where(Repo.name == repo_name)
    )
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_name}")
    return repo.id


@router.post("/query", response_model=RAGResponse)
async def query_rag(
    query: RAGQuery,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Query RAG system for code intelligence.
    
    Args:
        query: RAG query request
        session: Database session
        
    Returns:
        RAG response with answer and citations
    """
    try:
        # Get repository ID
        repo_id = await get_repo_id(query.repo, session)
        
        # Initialize components
        embedder = Embedder(
            model_name=getattr(settings, 'embedding_model_name', 'all-MiniLM-L6-v2')
        )
        retriever = HybridRetriever(session, embedder)
        generator = ResponseGenerator()
        
        # Retrieve relevant chunks
        chunks = await retriever.retrieve(
            query=query.question,
            repo_id=repo_id,
            top_k=query.top_k,
            file_paths=query.files,
        )
        
        if not chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant code found for the query"
            )
        
        # Extract citations
        citations_data = retriever.extract_citations(chunks)
        citations = [Citation(**cite) for cite in citations_data]
        
        # Generate response
        response = generator.generate(
            query=query.question,
            chunks=chunks,
            citations=citations,
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing RAG query: {e}")
        raise HTTPException(status_code=500, detail=str(e))
