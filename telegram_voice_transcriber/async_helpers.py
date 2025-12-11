"""Async utilities for Streamlit integration."""
from __future__ import annotations

import asyncio
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: asyncio.coroutines) -> T:
    """Run an async coroutine from sync context, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Create new loop in thread if one is already running
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)
