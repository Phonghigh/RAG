"""SQLAlchemy domain models."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from apps.shared.db.base import Base


class Repo(Base):
    """Repository model."""
    
    __tablename__ = "repos"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    monorepo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    service_map: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    commits: Mapped[list["Commit"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        back_populates="repo", cascade="all, delete-orphan"
    )
    diffs: Mapped[list["Diff"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="repo", cascade="all, delete-orphan"
    )
    rag_chunks: Mapped[list["RagChunk"]] = relationship(
        back_populates="repo", cascade="all, delete-orphan"
    )


class Commit(Base):
    """Commit model."""
    
    __tablename__ = "commits"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    sha: Mapped[str] = mapped_column(CHAR(40), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    added_loc: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    removed_loc: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    files_changed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="commits")
    diffs: Mapped[list["Diff"]] = relationship(back_populates="commit", cascade="all, delete-orphan")
    test_artifacts: Mapped[list["TestArtifact"]] = relationship(
        back_populates="commit", cascade="all, delete-orphan"
    )


class PullRequest(Base):
    """Pull Request model."""
    
    __tablename__ = "pull_requests"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_branch: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    head_sha: Mapped[Optional[str]] = mapped_column(CHAR(40), nullable=True)
    created_at_db: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="pull_requests")
    diffs: Mapped[list["Diff"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )
    test_artifacts: Mapped[list["TestArtifact"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan"
    )


class Diff(Base):
    """Diff model."""
    
    __tablename__ = "diffs"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    pr_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True
    )
    commit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("commits.id", ondelete="CASCADE"), nullable=True
    )
    path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lang: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_loc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    removed_loc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    object_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="diffs")
    pull_request: Mapped["PullRequest"] = relationship(back_populates="diffs")
    commit: Mapped["Commit"] = relationship(back_populates="diffs")


class Finding(Base):
    """Finding model."""
    
    __tablename__ = "findings"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    pr_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True
    )
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    suggestion: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    owner_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="findings")
    pull_request: Mapped["PullRequest"] = relationship(back_populates="findings")


class TestArtifact(Base):
    """Test Artifact model."""
    
    __tablename__ = "test_artifacts"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pr_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True
    )
    commit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("commits.id", ondelete="CASCADE"), nullable=True
    )
    framework: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    passed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    failed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    skipped: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    coverage_line: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    coverage_branch: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    object_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    pull_request: Mapped["PullRequest"] = relationship(back_populates="test_artifacts")
    commit: Mapped["Commit"] = relationship(back_populates="test_artifacts")


class Notification(Base):
    """Notification model."""
    
    __tablename__ = "notifications"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pr_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=True
    )
    channel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    pull_request: Mapped["PullRequest"] = relationship(back_populates="notifications")


class Audit(Base):
    """Audit trail model."""
    
    __tablename__ = "audits"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class RagChunk(Base):
    """RAG Chunk model for vector storage."""
    
    __tablename__ = "rag_chunks"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lang: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(CHAR(40), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ast_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        # Note: pgvector type will be handled at DB level
        type_=None,  # Will be set to vector(1536) in migration
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="rag_chunks")

