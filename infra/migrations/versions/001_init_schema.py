"""Initial schema

Revision ID: 001_init_schema
Revises: 
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_init_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Core entities
    op.create_table(
        'repos',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('monorepo', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('service_map', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    op.create_table(
        'commits',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('repo_id', sa.BigInteger(), nullable=True),
        sa.Column('sha', sa.CHAR(length=40), nullable=False),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('authored_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('added_loc', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('removed_loc', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('files_changed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repo_id', 'sha', name='uq_commits_repo_sha')
    )
    
    op.create_table(
        'pull_requests',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('repo_id', sa.BigInteger(), nullable=True),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state', sa.Text(), nullable=True),
        sa.Column('base_branch', sa.Text(), nullable=True),
        sa.Column('head_sha', sa.CHAR(length=40), nullable=True),
        sa.Column('created_at_db', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repo_id', 'number', name='uq_prs_repo_number')
    )
    
    op.create_table(
        'diffs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('repo_id', sa.BigInteger(), nullable=True),
        sa.Column('pr_id', sa.BigInteger(), nullable=True),
        sa.Column('commit_id', sa.BigInteger(), nullable=True),
        sa.Column('path', sa.Text(), nullable=True),
        sa.Column('lang', sa.Text(), nullable=True),
        sa.Column('added_loc', sa.Integer(), nullable=True),
        sa.Column('removed_loc', sa.Integer(), nullable=True),
        sa.Column('hunk_count', sa.Integer(), nullable=True),
        sa.Column('object_uri', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pr_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['commit_id'], ['commits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'findings',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('repo_id', sa.BigInteger(), nullable=True),
        sa.Column('pr_id', sa.BigInteger(), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('rule_id', sa.Text(), nullable=True),
        sa.Column('severity', sa.Text(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('suggestion', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('owner_hint', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Numeric(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pr_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'test_artifacts',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('pr_id', sa.BigInteger(), nullable=True),
        sa.Column('commit_id', sa.BigInteger(), nullable=True),
        sa.Column('framework', sa.Text(), nullable=True),
        sa.Column('passed', sa.Integer(), nullable=True),
        sa.Column('failed', sa.Integer(), nullable=True),
        sa.Column('skipped', sa.Integer(), nullable=True),
        sa.Column('coverage_line', sa.Numeric(), nullable=True),
        sa.Column('coverage_branch', sa.Numeric(), nullable=True),
        sa.Column('object_uri', sa.Text(), nullable=True),
        sa.Column('conclusion', sa.Text(), nullable=True),
        sa.Column('html_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['pr_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['commit_id'], ['commits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'notifications',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('pr_id', sa.BigInteger(), nullable=True),
        sa.Column('channel', sa.Text(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('delivered', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['pr_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'audits',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('actor', sa.Text(), nullable=True),
        sa.Column('action', sa.Text(), nullable=True),
        sa.Column('entity', sa.Text(), nullable=True),
        sa.Column('entity_id', sa.BigInteger(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('idx_commits_repo_sha', 'commits', ['repo_id', 'sha'])
    op.create_index('idx_commits_authored_at', 'commits', ['authored_at'])
    op.create_index('idx_prs_repo_number', 'pull_requests', ['repo_id', 'number'])
    op.create_index('idx_prs_state', 'pull_requests', ['state'])
    op.create_index('idx_diffs_repo_pr', 'diffs', ['repo_id', 'pr_id'])
    op.create_index('idx_diffs_commit', 'diffs', ['commit_id'])
    op.create_index('idx_findings_pr', 'findings', ['pr_id'])
    op.create_index('idx_findings_severity', 'findings', ['severity'])
    op.create_index('idx_notifications_pr', 'notifications', ['pr_id'])
    op.create_index('idx_notifications_delivered', 'notifications', ['delivered'])
    op.create_index('idx_audits_entity', 'audits', ['entity', 'entity_id'])
    op.create_index('idx_audits_at', 'audits', ['at'])


def downgrade() -> None:
    op.drop_index('idx_audits_at', table_name='audits')
    op.drop_index('idx_audits_entity', table_name='audits')
    op.drop_index('idx_notifications_delivered', table_name='notifications')
    op.drop_index('idx_notifications_pr', table_name='notifications')
    op.drop_index('idx_findings_severity', table_name='findings')
    op.drop_index('idx_findings_pr', table_name='findings')
    op.drop_index('idx_diffs_commit', table_name='diffs')
    op.drop_index('idx_diffs_repo_pr', table_name='diffs')
    op.drop_index('idx_prs_state', table_name='pull_requests')
    op.drop_index('idx_prs_repo_number', table_name='pull_requests')
    op.drop_index('idx_commits_authored_at', table_name='commits')
    op.drop_index('idx_commits_repo_sha', table_name='commits')
    
    op.drop_table('audits')
    op.drop_table('notifications')
    op.drop_table('test_artifacts')
    op.drop_table('findings')
    op.drop_table('diffs')
    op.drop_table('pull_requests')
    op.drop_table('commits')
    op.drop_table('repos')

