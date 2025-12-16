"""Add pgvector extension and rag_chunks table

Revision ID: 002_add_pgvector
Revises: 001_init_schema
Create Date: 2025-01-15 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_pgvector'
down_revision: Union[str, None] = '001_init_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create rag_chunks table
    op.create_table(
        'rag_chunks',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('repo_id', sa.BigInteger(), nullable=True),
        sa.Column('source_type', sa.Text(), nullable=True),
        sa.Column('source_id', sa.Text(), nullable=True),
        sa.Column('path', sa.Text(), nullable=True),
        sa.Column('lang', sa.Text(), nullable=True),
        sa.Column('commit_sha', sa.CHAR(length=40), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('ast_signature', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding', sa.dialects.postgresql.ARRAY(sa.Float()), nullable=True),  # Will be converted to vector type
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Convert embedding column to vector type (1536 dimensions)
    op.execute("""
        ALTER TABLE rag_chunks 
        ALTER COLUMN embedding TYPE vector(1536) 
        USING embedding::vector(1536)
    """)
    
    # Create indexes
    op.create_index('idx_rag_chunks_repo', 'rag_chunks', ['repo_id'])
    op.create_index('idx_rag_chunks_source', 'rag_chunks', ['source_type', 'source_id'])
    op.create_index('idx_rag_chunks_path', 'rag_chunks', ['path'])
    op.create_index('idx_rag_chunks_lang', 'rag_chunks', ['lang'])
    
    # Create ivfflat index for vector similarity search
    op.execute("""
        CREATE INDEX idx_rag_chunks_embedding ON rag_chunks 
        USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.drop_index('idx_rag_chunks_embedding', table_name='rag_chunks')
    op.drop_index('idx_rag_chunks_lang', table_name='rag_chunks')
    op.drop_index('idx_rag_chunks_path', table_name='rag_chunks')
    op.drop_index('idx_rag_chunks_source', table_name='rag_chunks')
    op.drop_index('idx_rag_chunks_repo', table_name='rag_chunks')
    
    op.drop_table('rag_chunks')
    
    # Note: We don't drop the vector extension as it might be used elsewhere

