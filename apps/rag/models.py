"""RAG query models."""
from pydantic import BaseModel, Field
from typing import Optional, List


class RAGQuery(BaseModel):
    """RAG query request."""
    question: str = Field(..., description="Question to answer")
    repo: str = Field(..., description="Repository name")
    branch: Optional[str] = Field(None, description="Branch name")
    files: Optional[List[str]] = Field(None, description="Filter by file paths")
    top_k: int = Field(5, description="Number of chunks to retrieve")


class Citation(BaseModel):
    """Citation for a code reference."""
    path: str = Field(..., description="File path")
    commit: Optional[str] = Field(None, description="Commit SHA")
    lines: Optional[List[int]] = Field(None, description="Line numbers")
    score: float = Field(..., description="Similarity score")


class RAGResponse(BaseModel):
    """RAG query response."""
    answer: str = Field(..., description="Generated answer")
    citations: List[Citation] = Field(..., description="Code citations")
    chunks: List[dict] = Field(default_factory=list, description="Retrieved chunks")
