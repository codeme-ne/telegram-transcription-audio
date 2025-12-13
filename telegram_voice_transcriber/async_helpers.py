"""Async utilities for Streamlit integration."""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

# Persistent event loop for Telethon - must stay the same after connection
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """Get or create the persistent event loop running in a background thread."""
    global _loop, _loop_thread

    if _loop is None or not _loop.is_running():
        _loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()

        _loop_thread = threading.Thread(target=run_loop, daemon=True)
        _loop_thread.start()

    return _loop


def run_async(coro: asyncio.coroutines) -> T:
    """Run an async coroutine using the persistent event loop."""
    loop = _get_or_create_loop()

    # If already inside any running loop (including our own), offload to a fresh loop
    # in a worker thread to avoid deadlocks and RuntimeError from asyncio.run().
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
