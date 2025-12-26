"""Test script to verify JSONB fix."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from apps.shared.db import Base


async def test():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Schema created successfully! JSONB compilation error is fixed.')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(test())
