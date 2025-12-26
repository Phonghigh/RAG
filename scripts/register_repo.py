#!/usr/bin/env python3
"""Manually register a repository in the database.

Usage:
    python scripts/register_repo.py <repo-name>
    python scripts/register_repo.py your-org/your-repo

Example:
    python scripts/register_repo.py myorg/myrepo
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from apps.shared.db.models import Repo
from apps.shared.config import settings


async def register_repo(repo_name: str, monorepo: bool = True, service_map: dict = None):
    """Register a repository in the database.
    
    Args:
        repo_name: Repository name in format 'org/repo'
        monorepo: Whether this is a monorepo (default: True)
        service_map: Optional service map configuration
        
    Returns:
        Repository ID
    """
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if repo exists
        existing = await session.scalar(
            select(Repo).where(Repo.name == repo_name)
        )
        
        if existing:
            print(f"✓ Repository '{repo_name}' already exists")
            print(f"  ID: {existing.id}")
            print(f"  Monorepo: {existing.monorepo}")
            print(f"  Created: {existing.created_at}")
            return existing.id
        
        # Create new repo
        repo = Repo(
            name=repo_name,
            monorepo=monorepo,
            service_map=service_map or {}
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        
        print(f"✓ Successfully registered repository: '{repo_name}'")
        print(f"  ID: {repo.id}")
        print(f"  Monorepo: {repo.monorepo}")
        print(f"  Created: {repo.created_at}")
        return repo.id


async def list_repos():
    """List all registered repositories."""
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        repos = await session.scalars(select(Repo).order_by(Repo.created_at))
        repo_list = list(repos)
        
        if not repo_list:
            print("No repositories registered.")
            return
        
        print(f"\nRegistered Repositories ({len(repo_list)}):")
        print("-" * 80)
        for repo in repo_list:
            print(f"  ID: {repo.id:4d} | Name: {repo.name:40s} | Monorepo: {repo.monorepo}")
        print("-" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/register_repo.py <repo-name>")
        print("       python scripts/register_repo.py --list")
        print("\nExample:")
        print("  python scripts/register_repo.py myorg/myrepo")
        print("  python scripts/register_repo.py --list")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        asyncio.run(list_repos())
        return
    
    repo_name = sys.argv[1]
    
    # Validate format
    if "/" not in repo_name:
        print(f"Error: Repository name must be in format 'org/repo', got '{repo_name}'")
        sys.exit(1)
    
    try:
        repo_id = asyncio.run(register_repo(repo_name))
        print(f"\nRepository ID: {repo_id}")
        print("\nNext steps:")
        print("  1. Configure GitHub webhook pointing to your API")
        print("  2. Make a test commit or create a PR")
        print("  3. Check logs to verify processing")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

