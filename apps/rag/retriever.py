"""Hybrid retrieval (BM25 + vector)."""
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from apps.shared.db.models import RagChunk, Repo
from apps.indexer.embedder import Embedder
from apps.indexer.vector_store import VectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval combining BM25 and vector search."""
    
    def __init__(self, session: AsyncSession, embedder: Embedder):
        """Initialize retriever."""
        self.session = session
        self.embedder = embedder
        self.vector_store = VectorStore(session)
        self.bm25_weight = 0.3
        self.vector_weight = 0.7
    
    async def retrieve(
        self,
        query: str,
        repo_id: int,
        top_k: int = 5,
        file_paths: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Retrieve relevant chunks using hybrid search.
        
        Args:
            query: Query string
            repo_id: Repository ID
            top_k: Number of results
            file_paths: Optional file path filter
            
        Returns:
            List of retrieved chunks with scores
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_single(query)
        
        # Vector search
        vector_results = await self.vector_store.search_similar(
            query_embedding=query_embedding,
            repo_id=repo_id,
            top_k=top_k * 2,  # Get more for hybrid scoring
        )
        
        # BM25 search (using PostgreSQL full-text search)
        bm25_results = await self._bm25_search(
            query=query,
            repo_id=repo_id,
            top_k=top_k * 2,
            file_paths=file_paths,
        )
        
        # Combine and re-rank
        combined_results = self._combine_results(vector_results, bm25_results)
        
        # Sort by combined score and return top_k
        combined_results.sort(key=lambda x: x['combined_score'], reverse=True)
        
        return combined_results[:top_k]
    
    async def _bm25_search(
        self,
        query: str,
        repo_id: int,
        top_k: int,
        file_paths: Optional[List[str]] = None,
    ) -> List[Dict]:
        """BM25 search using PostgreSQL full-text search or simple text search for SQLite."""
        # Check if we're using SQLite (for testing)
        dialect = self.session.bind.dialect.name if self.session.bind else None
        
        if dialect == 'sqlite':
            # SQLite doesn't support PostgreSQL full-text search, use simple LIKE search
            query_words = query.lower().split()
            conditions = [
                RagChunk.content.like(f"%{word}%") for word in query_words
            ]
            
            query_stmt = select(RagChunk).where(
                RagChunk.repo_id == repo_id,
                or_(*conditions)
            )
            
            if file_paths:
                query_stmt = query_stmt.where(
                    or_(*[RagChunk.path.like(f"%{path}%") for path in file_paths])
                )
            
            query_stmt = query_stmt.limit(top_k)
            
            results = await self.session.execute(query_stmt)
            
            bm25_results = []
            for chunk in results.scalars():
                # Simple scoring: count query word matches
                content_lower = (chunk.content or '').lower()
                matches = sum(1 for word in query_words if word in content_lower)
                score = min(1.0, matches / len(query_words)) if query_words else 0.0
                
                bm25_results.append({
                    'chunk_id': chunk.id,
                    'content': chunk.content,
                    'path': chunk.path,
                    'commit_sha': chunk.commit_sha,
                    'ast_signature': chunk.ast_signature,
                    'metadata': chunk.metadata_,
                    'bm25_score': score,
                })
            
            # Sort by score
            bm25_results.sort(key=lambda x: x['bm25_score'], reverse=True)
            return bm25_results[:top_k]
        else:
            # PostgreSQL full-text search
            query_stmt = select(
                RagChunk,
                func.ts_rank_cd(
                    func.to_tsvector('english', RagChunk.content),
                    func.plainto_tsquery('english', query)
                ).label('rank')
            ).where(
                RagChunk.repo_id == repo_id,
                func.to_tsvector('english', RagChunk.content).match(
                    func.plainto_tsquery('english', query)
                )
            )
            
            if file_paths:
                query_stmt = query_stmt.where(
                    or_(*[RagChunk.path.like(f"%{path}%") for path in file_paths])
                )
            
            query_stmt = query_stmt.order_by('rank').limit(top_k)
            
            results = await self.session.execute(query_stmt)
            
            bm25_results = []
            for row in results:
                chunk = row[0]
                rank = row[1]
                
                # Normalize rank to 0-1 score
                score = min(1.0, float(rank) / 10.0)  # Rough normalization
                
                bm25_results.append({
                    'chunk_id': chunk.id,
                    'content': chunk.content,
                    'path': chunk.path,
                    'commit_sha': chunk.commit_sha,
                    'ast_signature': chunk.ast_signature,
                    'metadata': chunk.metadata_,
                    'bm25_score': score,
                })
            
            return bm25_results
    
    def _combine_results(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict]
    ) -> List[Dict]:
        """Combine vector and BM25 results with weighted scores."""
        # Create map of chunk_id -> results
        combined_map = {}
        
        # Add vector results
        for result in vector_results:
            chunk_id = result['chunk_id']
            combined_map[chunk_id] = {
                **result,
                'vector_score': result.get('similarity', 0.0),
                'bm25_score': 0.0,
            }
        
        # Add/update BM25 results
        for result in bm25_results:
            chunk_id = result['chunk_id']
            if chunk_id in combined_map:
                combined_map[chunk_id]['bm25_score'] = result.get('bm25_score', 0.0)
            else:
                combined_map[chunk_id] = {
                    **result,
                    'vector_score': 0.0,
                    'bm25_score': result.get('bm25_score', 0.0),
                }
        
        # Calculate combined scores
        combined_results = []
        for chunk_id, result in combined_map.items():
            combined_score = (
                result['vector_score'] * self.vector_weight +
                result['bm25_score'] * self.bm25_weight
            )
            
            result['combined_score'] = combined_score
            combined_results.append(result)
        
        return combined_results
    
    def extract_citations(self, chunks: List[Dict]) -> List[Dict]:
        """Extract citations from retrieved chunks."""
        citations = []
        
        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            path = chunk.get('path', '')
            commit_sha = chunk.get('commit_sha')
            
            # Extract line numbers from metadata if available
            lines = None
            if 'start_line' in metadata and 'end_line' in metadata:
                lines = list(range(metadata['start_line'], metadata['end_line'] + 1))
            
            citations.append({
                'path': path,
                'commit': commit_sha,
                'lines': lines,
                'score': chunk.get('combined_score', chunk.get('similarity', 0.0)),
            })
        
        return citations
