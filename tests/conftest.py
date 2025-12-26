"""Pytest configuration and fixtures."""
import sys
import pytest
import asyncio
import selectors

# Fix Windows event loop issue for psycopg
if sys.platform == 'win32':
    # Use SelectorEventLoop instead of ProactorEventLoop on Windows
    # This is required for psycopg compatibility
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

