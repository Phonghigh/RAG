"""pgvector storage operations."""
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apps.shared.db.models import RagChunk, Repo

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages pgvector storage operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize vector store."""
        self.session = session
    
    async def upsert_chunks(
        self,
        repo_id: int,
        chunks: List[Dict],
        source_type: str = "function",
        source_id: Optional[str] = None,
        commit_sha: Optional[str] = None,
        path: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> int:
        """
        Upsert chunks into vector store.
        
        Args:
            repo_id: Repository ID
            chunks: List of chunk dicts with 'content', 'metadata', 'ast_signature', 'embedding'
            source_type: Type of source (function, file, pr_diff)
            source_id: Optional source ID
            commit_sha: Optional commit SHA
            path: Optional file path
            lang: Optional language
            
        Returns:
            Number of chunks upserted
        """
        upserted = 0
        
        for chunk in chunks:
            content = chunk.get('content', '')
            metadata = chunk.get('metadata', {})
            ast_signature = chunk.get('ast_signature')
            embedding = chunk.get('embedding')
            
            if not content or not embedding:
                logger.warning("Skipping chunk without content or embedding")
                continue
            
            # Check if chunk already exists (by source_id + ast_signature)
            existing = None
            if source_id and ast_signature:
                existing = await self.session.scalar(
                    select(RagChunk).where(
                        RagChunk.repo_id == repo_id,
                        RagChunk.source_id == source_id,
                        RagChunk.ast_signature == ast_signature,
                    )
                )
            
            if existing:
                # Update existing chunk
                existing.content = content
                existing.metadata_ = metadata
                existing.embedding = embedding
                existing.commit_sha = commit_sha
                upserted += 1
            else:
                # Create new chunk
                rag_chunk = RagChunk(
                    repo_id=repo_id,
                    source_type=source_type,
                    source_id=source_id,
                    path=path,
                    lang=lang,
                    commit_sha=commit_sha,
                    content=content,
                    ast_signature=ast_signature,
                    metadata_=metadata,
                    embedding=embedding,
                )
                self.session.add(rag_chunk)
                upserted += 1
        
        await self.session.flush()
        logger.info(f"Upserted {upserted} chunks for repo_id={repo_id}")
        
        return upserted
    
    async def search_similar(
        self,
        query_embedding: List[float],
        repo_id: Optional[int] = None,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> List[Dict]:
        """
        Search for similar chunks using vector similarity.
        
        Args:
            query_embedding: Query embedding vector
            repo_id: Optional repository ID to filter
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar chunks with scores
        """
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import func
        import math
        
        # Check if we're using SQLite (for testing)
        dialect = self.session.bind.dialect.name if self.session.bind else None
        
        if dialect == 'sqlite':
            # SQLite doesn't support cosine_distance, calculate in Python
            query = select(RagChunk)
            if repo_id:
                query = query.where(RagChunk.repo_id == repo_id)
            
            results = await self.session.execute(query)
            chunks_with_similarity = []
            
            for chunk in results.scalars():
                if not chunk.embedding:
                    continue
                
                # Calculate cosine similarity in Python
                embedding = chunk.embedding if isinstance(chunk.embedding, list) else chunk.embedding
                similarity = self._cosine_similarity(query_embedding, embedding)
                
                if similarity >= threshold:
                    chunks_with_similarity.append({
                        'chunk_id': chunk.id,
                        'content': chunk.content,
                        'path': chunk.path,
                        'commit_sha': chunk.commit_sha,
                        'ast_signature': chunk.ast_signature,
                        'metadata': chunk.metadata_,
                        'similarity': similarity,
                        'distance': 1.0 - similarity,
                    })
            
            # Sort by similarity (descending) and return top_k
            chunks_with_similarity.sort(key=lambda x: x['similarity'], reverse=True)
            return chunks_with_similarity[:top_k]
        else:
            # PostgreSQL with pgvector - use SQL function
            query = select(
                RagChunk,
                func.cosine_distance(RagChunk.embedding, query_embedding).label('distance')
            )
            
            if repo_id:
                query = query.where(RagChunk.repo_id == repo_id)
            
            # Order by similarity (lower distance = more similar)
            query = query.order_by('distance').limit(top_k)
            
            results = await self.session.execute(query)
            
            similar_chunks = []
            for row in results:
                chunk = row[0]
                distance = row[1]
                
                # Convert distance to similarity (1 - distance)
                similarity = 1.0 - distance
                
                if similarity >= threshold:
                    similar_chunks.append({
                        'chunk_id': chunk.id,
                        'content': chunk.content,
                        'path': chunk.path,
                        'commit_sha': chunk.commit_sha,
                        'ast_signature': chunk.ast_signature,
                        'metadata': chunk.metadata_,
                        'similarity': similarity,
                        'distance': distance,
                    })
            
            return similar_chunks
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
