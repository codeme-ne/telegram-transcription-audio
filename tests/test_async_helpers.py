import asyncio
import pytest
from telegram_voice_transcriber.async_helpers import run_async


def test_run_async_executes_coroutine():
    async def sample_coro():
        return 42

    result = run_async(sample_coro())
    assert result == 42


def test_run_async_handles_existing_loop():
    async def outer():
        async def inner():
            return "nested"
        return run_async(inner())

    # This tests that run_async works even if called from sync context
    result = run_async(outer())
    assert result == "nested"
