"""Response generation with citations."""
import logging
from typing import List, Dict
from apps.rag.models import Citation, RAGResponse

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates RAG responses with citations."""
    
    def generate(
        self,
        query: str,
        chunks: List[Dict],
        citations: List[Citation],
    ) -> RAGResponse:
        """
        Generate response from retrieved chunks.
        
        Args:
            query: Original query
            chunks: Retrieved chunks
            citations: Extracted citations
            
        Returns:
            RAG response with answer and citations
        """
        # Build answer from chunks
        answer_parts = []
        
        # Add summary from top chunks
        answer_parts.append("Based on the codebase:")
        
        for i, chunk in enumerate(chunks[:3], 1):  # Use top 3 chunks
            content = chunk.get('content', '')
            # Truncate long content
            if len(content) > 500:
                content = content[:500] + "..."
            
            answer_parts.append(f"\n\n[{i}] {content}")
        
        # Add citations
        answer_parts.append("\n\nReferences:")
        for citation in citations:
            citation_str = citation.path
            if citation.commit:
                citation_str += f" (commit: {citation.commit[:8]})"
            if citation.lines:
                citation_str += f" lines {citation.lines[0]}-{citation.lines[-1]}"
            answer_parts.append(f"- {citation_str}")
        
        answer = "\n".join(answer_parts)
        
        return RAGResponse(
            answer=answer,
            citations=citations,
            chunks=[{
                'content': chunk.get('content', ''),
                'path': chunk.get('path'),
                'score': chunk.get('combined_score', 0.0),
            } for chunk in chunks],
        )
