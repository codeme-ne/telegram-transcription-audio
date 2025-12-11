# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A CLI tool that exports voice messages from Telegram chats, transcribes them locally using Whisper (faster-whisper), and outputs the results as Markdown. Runs fully offline without Telegram Premium.

## Commands

```bash
# Install in development mode
pip install -e '.[dev]'

# Run all tests
pytest

# Run a single test file
pytest tests/test_pipeline.py

# Run a specific test
pytest tests/test_pipeline.py::test_pipeline_creates_dry_run_stats

# CLI usage (requires TG_API_ID and TG_API_HASH env vars)
tg-transcribe "Chat Name" --year 2025 --dry-run
```

## Architecture

### Data Flow

1. **TelegramCollector** (`tg_client.py`) - Connects to Telegram via Telethon, iterates messages, and creates `MessageEnvelope` objects
2. **ProcessingPipeline** (`pipeline.py`) - Orchestrates the processing flow using Protocol-based dependency injection
3. **MediaDownloader** (`download.py`) - Downloads voice/audio/video_note media to cache
4. **WhisperTranscriber** (`transcribe.py`) - Transcribes audio using faster-whisper (lazily loaded)
5. **MarkdownExporter** (`export_md.py`) - Renders `TranscriptEntry` objects to Markdown
6. **ProcessingState** (`state.py`) - Persists processed message IDs to enable resume

### Key Patterns

**Protocol-based DI**: `pipeline.py` defines `Downloader`, `Transcriber`, and `Writer` protocols. This allows easy stubbing in tests (see `test_pipeline.py` for `StubDownloader`, `StubTranscriber`, `MemoryWriter`).

**Message filtering**: Two-stage filtering via `FilterConfig`:
- Collection stage: `TelegramCollector.collect()` filters by date range and allowed types
- Processing stage: `should_include_message()` filters by sender, type, year, and include_self

**Lazy model loading**: Whisper model is only loaded when audio transcription is actually needed (checked via `requires_transcription()`).

**Resumable processing**: `ProcessingState` tracks processed message IDs in `state.json`, allowing interrupted runs to continue.

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Typer CLI, async entrypoint, Telegram auth flow |
| `config.py` | Configuration dataclasses, path computation, date range parsing |
| `filters.py` | `MessageType` enum, `FilterConfig`, `should_include_message()` |
| `models.py` | `MessageEnvelope`, `TranscriptEntry`, `MessageSummary` dataclasses |
| `pipeline.py` | `ProcessingPipeline` with dry-run and full-run modes |
| `tg_client.py` | `TelegramCollector` for message collection |
| `state.py` | `ProcessingState` for resume capability |
| `dry_run.py` | `DryRunReport` for preview statistics |

## Development Philosophy

- **TDD**: Tests first, no modification of passing tests
- **Async**: All Telegram operations are async (pytest-asyncio for tests)
- **German UI**: CLI messages and output are in German
