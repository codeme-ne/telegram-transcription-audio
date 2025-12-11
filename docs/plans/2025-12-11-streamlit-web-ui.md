# Streamlit Web UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wrap the existing CLI tool in a Streamlit web interface so users can transcribe Telegram voice messages through their browser.

**Architecture:** Multi-step wizard flow: API credentials → Telegram auth (phone/code/2FA) → Chat selection → Configuration → Processing with live progress → Download. All state managed via `st.session_state`. Async operations wrapped for Streamlit compatibility.

**Tech Stack:** Streamlit, existing telegram_voice_transcriber modules, asyncio integration

---

## Task 1: Add Streamlit Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add streamlit to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    "telethon>=1.34.0",
    "faster-whisper>=1.0.0",
    "tqdm>=4.66.0",
    "python-dateutil>=2.8.2",
    "tzlocal>=5.2",
    "rich>=13.7.0",
    "typer>=0.12.3",
    "streamlit>=1.40.0",
]
```

**Step 2: Reinstall package**

Run: `pip install -e '.[dev]'`
Expected: Successfully installed streamlit and dependencies

**Step 3: Verify streamlit works**

Run: `streamlit --version`
Expected: Prints version (1.40.x or higher)

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add streamlit dependency for web UI"
```

---

## Task 2: Create Async Helper Module

**Files:**
- Create: `telegram_voice_transcriber/async_helpers.py`
- Test: `tests/test_async_helpers.py`

**Step 1: Write the failing test**

Create `tests/test_async_helpers.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_async_helpers.py -v`
Expected: FAIL with "No module named 'telegram_voice_transcriber.async_helpers'"

**Step 3: Write minimal implementation**

Create `telegram_voice_transcriber/async_helpers.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_async_helpers.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add telegram_voice_transcriber/async_helpers.py tests/test_async_helpers.py
git commit -m "feat: add async helper for Streamlit compatibility"
```

---

## Task 3: Create Web Auth Manager

**Files:**
- Create: `telegram_voice_transcriber/web_auth.py`
- Test: `tests/test_web_auth.py`

**Step 1: Write the failing test**

Create `tests/test_web_auth.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram_voice_transcriber.web_auth import WebAuthManager, AuthState


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.is_user_authorized = AsyncMock(return_value=False)
    client.send_code_request = AsyncMock()
    client.sign_in = AsyncMock()
    client.get_me = AsyncMock(return_value=MagicMock(id=123, first_name="Test"))
    return client


def test_auth_manager_initial_state():
    manager = WebAuthManager()
    assert manager.state == AuthState.NEEDS_CREDENTIALS


def test_auth_manager_set_credentials():
    manager = WebAuthManager()
    manager.set_credentials(api_id=123456, api_hash="abc123")
    assert manager.state == AuthState.NEEDS_PHONE
    assert manager.api_id == 123456


@pytest.mark.asyncio
async def test_auth_manager_send_code(mock_client):
    manager = WebAuthManager()
    manager.set_credentials(api_id=123456, api_hash="abc123")
    manager._client = mock_client

    await manager.send_code("+1234567890")

    mock_client.send_code_request.assert_called_once_with("+1234567890")
    assert manager.state == AuthState.NEEDS_CODE
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_auth.py -v`
Expected: FAIL with "No module named 'telegram_voice_transcriber.web_auth'"

**Step 3: Write minimal implementation**

Create `telegram_voice_transcriber/web_auth.py`:

```python
"""Web-compatible Telegram authentication manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Any

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


class AuthState(Enum):
    NEEDS_CREDENTIALS = auto()
    NEEDS_PHONE = auto()
    NEEDS_CODE = auto()
    NEEDS_2FA = auto()
    AUTHENTICATED = auto()
    ERROR = auto()


@dataclass
class WebAuthManager:
    """Manages Telegram authentication flow for web UI."""

    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    phone: Optional[str] = None
    session_path: Path = field(default_factory=lambda: Path(".data/web.session"))
    state: AuthState = AuthState.NEEDS_CREDENTIALS
    error_message: Optional[str] = None
    user_info: Optional[dict] = None
    _client: Optional[TelegramClient] = field(default=None, repr=False)

    def set_credentials(self, api_id: int, api_hash: str) -> None:
        """Set API credentials and advance state."""
        self.api_id = api_id
        self.api_hash = api_hash
        self.state = AuthState.NEEDS_PHONE

    async def connect(self) -> None:
        """Initialize and connect the Telegram client."""
        if self._client is None:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            self._client = TelegramClient(
                str(self.session_path), self.api_id, self.api_hash
            )
        await self._client.connect()

        if await self._client.is_user_authorized():
            me = await self._client.get_me()
            self.user_info = {"id": me.id, "name": getattr(me, "first_name", str(me.id))}
            self.state = AuthState.AUTHENTICATED

    async def send_code(self, phone: str) -> None:
        """Send verification code to phone number."""
        self.phone = phone
        await self._client.send_code_request(phone)
        self.state = AuthState.NEEDS_CODE

    async def verify_code(self, code: str) -> None:
        """Verify the received code."""
        try:
            await self._client.sign_in(phone=self.phone, code=code)
            me = await self._client.get_me()
            self.user_info = {"id": me.id, "name": getattr(me, "first_name", str(me.id))}
            self.state = AuthState.AUTHENTICATED
        except SessionPasswordNeededError:
            self.state = AuthState.NEEDS_2FA

    async def verify_2fa(self, password: str) -> None:
        """Verify 2FA password."""
        await self._client.sign_in(password=password)
        me = await self._client.get_me()
        self.user_info = {"id": me.id, "name": getattr(me, "first_name", str(me.id))}
        self.state = AuthState.AUTHENTICATED

    async def disconnect(self) -> None:
        """Disconnect the client."""
        if self._client:
            await self._client.disconnect()

    @property
    def client(self) -> Optional[TelegramClient]:
        """Get the underlying Telegram client."""
        return self._client
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_auth.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add telegram_voice_transcriber/web_auth.py tests/test_web_auth.py
git commit -m "feat: add WebAuthManager for web-based Telegram auth"
```

---

## Task 4: Create Chat Listing Function

**Files:**
- Modify: `telegram_voice_transcriber/tg_client.py`
- Test: `tests/test_tg_client.py`

**Step 1: Write the failing test**

Add to `tests/test_tg_client.py`:

```python
@pytest.mark.asyncio
async def test_list_dialogs_returns_chat_list():
    mock_client = MagicMock()
    mock_dialog1 = MagicMock()
    mock_dialog1.name = "Alice"
    mock_dialog1.id = 123
    mock_dialog1.is_user = True
    mock_dialog1.is_group = False

    mock_dialog2 = MagicMock()
    mock_dialog2.name = "Work Group"
    mock_dialog2.id = 456
    mock_dialog2.is_user = False
    mock_dialog2.is_group = True

    async def mock_iter_dialogs():
        for d in [mock_dialog1, mock_dialog2]:
            yield d

    mock_client.iter_dialogs = mock_iter_dialogs

    from telegram_voice_transcriber.tg_client import list_dialogs
    dialogs = await list_dialogs(mock_client)

    assert len(dialogs) == 2
    assert dialogs[0]["name"] == "Alice"
    assert dialogs[0]["id"] == 123
    assert dialogs[1]["name"] == "Work Group"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tg_client.py::test_list_dialogs_returns_chat_list -v`
Expected: FAIL with "cannot import name 'list_dialogs'"

**Step 3: Write minimal implementation**

Add to `telegram_voice_transcriber/tg_client.py`:

```python
async def list_dialogs(client: Any, limit: int = 50) -> list[dict]:
    """List recent dialogs/chats for selection UI."""
    dialogs = []
    async for dialog in client.iter_dialogs(limit=limit):
        dialogs.append({
            "id": dialog.id,
            "name": dialog.name or str(dialog.id),
            "is_user": getattr(dialog, "is_user", False),
            "is_group": getattr(dialog, "is_group", False),
        })
    return dialogs
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tg_client.py::test_list_dialogs_returns_chat_list -v`
Expected: PASS

**Step 5: Commit**

```bash
git add telegram_voice_transcriber/tg_client.py tests/test_tg_client.py
git commit -m "feat: add list_dialogs for chat selection UI"
```

---

## Task 5: Create Main Streamlit App

**Files:**
- Create: `app.py` (root directory)

**Step 1: Create the Streamlit app structure**

Create `app.py`:

```python
"""Streamlit web UI for Telegram Voice Transcriber."""
from __future__ import annotations

import streamlit as st
from pathlib import Path

from telegram_voice_transcriber.async_helpers import run_async
from telegram_voice_transcriber.web_auth import WebAuthManager, AuthState
from telegram_voice_transcriber.tg_client import list_dialogs, TelegramCollector
from telegram_voice_transcriber.config import build_app_config
from telegram_voice_transcriber.download import MediaDownloader
from telegram_voice_transcriber.dry_run import DryRunReport
from telegram_voice_transcriber.export_md import MarkdownExporter
from telegram_voice_transcriber.filters import FilterConfig, MessageType
from telegram_voice_transcriber.pipeline import PipelineOptions, ProcessingPipeline
from telegram_voice_transcriber.state import ProcessingState
from telegram_voice_transcriber.transcribe import WhisperTranscriber
from telegram_voice_transcriber.writer import FileWriter

st.set_page_config(
    page_title="Telegram Voice Transcriber",
    page_icon="🎙️",
    layout="wide",
)

# Initialize session state
if "auth_manager" not in st.session_state:
    st.session_state.auth_manager = WebAuthManager()
if "dialogs" not in st.session_state:
    st.session_state.dialogs = []
if "processing" not in st.session_state:
    st.session_state.processing = False
if "result_markdown" not in st.session_state:
    st.session_state.result_markdown = None


def main():
    st.title("🎙️ Telegram Voice Transcriber")
    st.markdown("Transcribe Telegram voice messages locally using Whisper. No Premium required.")

    auth = st.session_state.auth_manager

    # Sidebar: Authentication
    with st.sidebar:
        st.header("🔐 Authentication")
        render_auth_section(auth)

    # Main content based on auth state
    if auth.state == AuthState.AUTHENTICATED:
        render_transcription_ui(auth)
    else:
        render_setup_instructions()


def render_auth_section(auth: WebAuthManager):
    """Render the authentication sidebar based on current state."""

    if auth.state == AuthState.NEEDS_CREDENTIALS:
        st.markdown("### Step 1: API Credentials")
        st.markdown("[Get credentials from my.telegram.org](https://my.telegram.org)")

        api_id = st.text_input("API ID", type="default")
        api_hash = st.text_input("API Hash", type="password")

        if st.button("Save Credentials", disabled=not (api_id and api_hash)):
            try:
                auth.set_credentials(api_id=int(api_id), api_hash=api_hash)
                run_async(auth.connect())
                if auth.state == AuthState.AUTHENTICATED:
                    st.success(f"Already logged in as {auth.user_info['name']}!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.NEEDS_PHONE:
        st.markdown("### Step 2: Phone Number")
        phone = st.text_input("Phone (with country code)", placeholder="+1234567890")

        if st.button("Send Code", disabled=not phone):
            try:
                run_async(auth.send_code(phone))
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.NEEDS_CODE:
        st.markdown("### Step 3: Verification Code")
        st.info(f"Code sent to {auth.phone}")
        code = st.text_input("Enter code")

        if st.button("Verify", disabled=not code):
            try:
                run_async(auth.verify_code(code))
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.NEEDS_2FA:
        st.markdown("### Step 3b: Two-Factor Authentication")
        password = st.text_input("2FA Password", type="password")

        if st.button("Submit", disabled=not password):
            try:
                run_async(auth.verify_2fa(password))
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    elif auth.state == AuthState.AUTHENTICATED:
        st.success(f"✅ Logged in as {auth.user_info['name']}")
        if st.button("Logout"):
            run_async(auth.disconnect())
            st.session_state.auth_manager = WebAuthManager()
            st.session_state.dialogs = []
            st.rerun()


def render_setup_instructions():
    """Show instructions while not authenticated."""
    st.info("👈 Complete authentication in the sidebar to start transcribing.")

    with st.expander("📖 How to get Telegram API credentials (2 minutes)"):
        st.markdown("""
        1. Go to [my.telegram.org](https://my.telegram.org)
        2. Log in with your phone number
        3. Click "API development tools"
        4. Create a new application (any name)
        5. Copy the **API ID** and **API Hash**

        These are your personal credentials - the app runs locally and your data never leaves your computer.
        """)


def render_transcription_ui(auth: WebAuthManager):
    """Main transcription interface when authenticated."""

    # Load dialogs if not loaded
    if not st.session_state.dialogs:
        with st.spinner("Loading your chats..."):
            st.session_state.dialogs = run_async(list_dialogs(auth.client))

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📋 Configuration")

        # Chat selection
        dialog_options = {d["name"]: d["id"] for d in st.session_state.dialogs}
        selected_chat = st.selectbox(
            "Select chat",
            options=list(dialog_options.keys()),
            help="Choose which chat to transcribe"
        )

        # Date/Year settings
        year = st.number_input("Year", min_value=2015, max_value=2025, value=2025)

        # Message types
        message_types = st.multiselect(
            "Message types",
            options=["voice", "audio", "video_note", "text"],
            default=["voice", "text"],
        )

    with col2:
        st.subheader("⚙️ Options")

        include_self = st.checkbox("Include my messages", value=False)
        language = st.selectbox("Language", ["de", "en", "fr", "es", "it"], index=0)
        model_size = st.selectbox(
            "Whisper model",
            ["tiny", "base", "small", "medium"],
            index=2,
            help="Larger = more accurate but slower"
        )
        dry_run = st.checkbox("Dry run (preview only)", value=True)

    st.divider()

    # Process button
    if st.button("🚀 Start Transcription", type="primary", use_container_width=True):
        if not selected_chat:
            st.error("Please select a chat")
            return

        process_transcription(
            auth=auth,
            chat_id=dialog_options[selected_chat],
            chat_name=selected_chat,
            year=year,
            message_types=message_types,
            include_self=include_self,
            language=language,
            model_size=model_size,
            dry_run=dry_run,
        )

    # Show results if available
    if st.session_state.result_markdown:
        st.divider()
        st.subheader("📄 Result")
        st.download_button(
            "⬇️ Download Markdown",
            data=st.session_state.result_markdown,
            file_name=f"transcript-{year}.md",
            mime="text/markdown",
        )
        with st.expander("Preview"):
            st.markdown(st.session_state.result_markdown[:5000] + "..." if len(st.session_state.result_markdown) > 5000 else st.session_state.result_markdown)


def process_transcription(
    auth: WebAuthManager,
    chat_id: int,
    chat_name: str,
    year: int,
    message_types: list[str],
    include_self: bool,
    language: str,
    model_size: str,
    dry_run: bool,
):
    """Run the transcription pipeline with progress updates."""

    base_dir = Path(".data/web")
    base_dir.mkdir(parents=True, exist_ok=True)

    config = build_app_config(
        api_id=auth.api_id,
        api_hash=auth.api_hash,
        session_file=auth.session_path,
        chat_identifier=str(chat_id),
        year=year,
        include_self=include_self,
        include_types=message_types,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
        dry_run=dry_run,
        language=language,
        model_size=model_size,
        base_dir=base_dir,
    )

    with st.status("Processing...", expanded=True) as status:
        # Collect messages
        st.write("📥 Collecting messages from Telegram...")
        collector = TelegramCollector(auth.client)
        collector_filter = FilterConfig(
            allowed_sender_ids=None,
            allowed_types=set(MessageType(t) for t in message_types),
            year=year,
            include_self=True,
        )

        collection = run_async(collector.collect(
            chat_identifier=chat_id,
            filter_config=collector_filter,
            since=config.date_range.since,
            until=config.date_range.until,
        ))

        st.write(f"Found {len(collection.messages)} messages")

        if not collection.messages:
            status.update(label="No messages found", state="complete")
            return

        # Setup pipeline
        state = ProcessingState(config.paths.state_path)
        downloader = MediaDownloader(client=auth.client, base_dir=config.paths.cache_dir)
        exporter = MarkdownExporter(
            chat_title=chat_name,
            year=year,
            include_message_ids=True,
            timezone_name=config.timezone,
        )
        dry_run_report = DryRunReport(chat_title=chat_name, year=year)

        # Determine sender filtering
        sender_ids = {m.sender_id for m in collection.messages if m.sender_id}
        if collection.self_user_id and not include_self:
            sender_ids.discard(collection.self_user_id)

        # Load Whisper model if needed
        if not dry_run:
            st.write(f"🤖 Loading Whisper model ({model_size})...")
            from faster_whisper import WhisperModel
            models_dir = config.paths.cache_dir.parent / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            model = WhisperModel(model_size, device="auto", compute_type="int8", download_root=str(models_dir))
            transcriber = WhisperTranscriber(model=model, language=language)
        else:
            transcriber = _DummyTranscriber()

        pipeline = ProcessingPipeline(
            options=PipelineOptions(dry_run=dry_run, output_path=config.paths.output_path),
            filter_config=FilterConfig(
                allowed_sender_ids=sender_ids or None,
                allowed_types=set(MessageType(t) for t in message_types),
                year=year,
                include_self=include_self,
            ),
            exporter=exporter,
            dry_run_report=dry_run_report,
            downloader=downloader,
            transcriber=transcriber,
            writer=FileWriter(),
            state=state,
            self_user_id=collection.self_user_id,
        )

        # Run pipeline
        st.write("⚙️ Processing messages...")
        result = run_async(pipeline.run(collection.messages))

        if dry_run:
            status.update(label="Dry run complete!", state="complete")
            st.write(f"Would process {result.total_messages} messages")
            for msg_type, count in result.type_counts.items():
                st.write(f"  - {msg_type.value}: {count}")
        else:
            status.update(label="Transcription complete!", state="complete")
            st.write(f"Processed {result.processed_messages} messages")

            # Load result for download
            if result.output_path and result.output_path.exists():
                st.session_state.result_markdown = result.output_path.read_text()


class _DummyTranscriber:
    def transcribe(self, audio_path):
        return "[Dry run - no transcription]"


if __name__ == "__main__":
    main()
```

**Step 2: Run the app to verify it starts**

Run: `streamlit run app.py`
Expected: Browser opens with the app UI showing authentication form

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit web UI for transcription"
```

---

## Task 6: Add Streamlit Run Script

**Files:**
- Modify: `pyproject.toml`
- Create: `README.md` section

**Step 1: Add script entry point**

In `pyproject.toml`, add to `[project.scripts]`:

```toml
[project.scripts]
tg-transcribe = "telegram_voice_transcriber.cli:main"
tg-web = "telegram_voice_transcriber.web:run"
```

**Step 2: Create web runner module**

Create `telegram_voice_transcriber/web.py`:

```python
"""Web UI launcher."""
import subprocess
import sys
from pathlib import Path


def run():
    """Launch the Streamlit web UI."""
    app_path = Path(__file__).parent.parent / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])
```

**Step 3: Update README.md**

Add to README.md after the CLI section:

```markdown
## Web UI

```bash
# Start the web interface
streamlit run app.py

# Or using the installed command
tg-web
```

Open http://localhost:8501 in your browser.
```

**Step 4: Commit**

```bash
git add pyproject.toml telegram_voice_transcriber/web.py README.md
git commit -m "feat: add tg-web command and update README"
```

---

## Task 7: Create Dockerfile for Easy Deployment

**Files:**
- Create: `Dockerfile`
- Create: `.streamlit/config.toml`

**Step 1: Create Streamlit config**

Create `.streamlit/config.toml`:

```toml
[server]
headless = true
port = 8501
enableCORS = false

[theme]
primaryColor = "#0088cc"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
```

**Step 2: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY telegram_voice_transcriber ./telegram_voice_transcriber
COPY app.py ./
COPY .streamlit ./.streamlit

# Install Python package
RUN pip install --no-cache-dir -e .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```

**Step 3: Test Docker build**

Run: `docker build -t telegram-transcriber .`
Expected: Image builds successfully

**Step 4: Test Docker run**

Run: `docker run -p 8501:8501 telegram-transcriber`
Expected: App accessible at http://localhost:8501

**Step 5: Commit**

```bash
git add Dockerfile .streamlit/config.toml
git commit -m "feat: add Docker support for easy deployment"
```

---

## Task 8: Update README for Portfolio

**Files:**
- Modify: `README.md`

**Step 1: Rewrite README in English with better structure**

Replace `README.md` with:

```markdown
# 🎙️ Telegram Voice Transcriber

Export and transcribe Telegram voice messages locally using Whisper AI. **No Telegram Premium required.**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- 🔒 **Privacy-first**: All processing happens locally - your data never leaves your machine
- 🎯 **Smart filtering**: Filter by sender, message type, date range
- 🔄 **Resumable**: Pick up where you left off with automatic state tracking
- 📱 **No Premium needed**: Uses Telegram's free API, not premium features
- 🌐 **Web UI**: Simple browser interface with Streamlit
- 💻 **CLI**: Full-featured command line for automation

## Quick Start

### Web UI (Recommended)

```bash
# Install
pip install -e .

# Run
streamlit run app.py
```

Open http://localhost:8501 and follow the guided setup.

### Docker

```bash
docker build -t telegram-transcriber .
docker run -p 8501:8501 telegram-transcriber
```

### CLI

```bash
# Set your API credentials
export TG_API_ID=your_id
export TG_API_HASH=your_hash

# Preview (dry run)
tg-transcribe "Chat Name" --year 2025 --dry-run

# Full transcription
tg-transcribe "Chat Name" --year 2025
```

## Getting Telegram API Credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click "API development tools"
4. Create a new application
5. Copy **API ID** and **API Hash**

This takes about 2 minutes and is completely free.

## How It Works

1. **Connect**: Authenticate with your Telegram account
2. **Select**: Choose a chat and configure filters
3. **Process**: Voice messages are downloaded and transcribed locally
4. **Export**: Get a clean Markdown file organized by date

## Requirements

- Python 3.10+
- ffmpeg (`sudo apt install ffmpeg` on Ubuntu)
- ~2GB disk space for Whisper models (downloaded on first use)

## Tech Stack

- **Telethon**: Telegram MTProto client
- **faster-whisper**: Optimized Whisper inference
- **Streamlit**: Web UI framework
- **Typer**: CLI framework

## Development

```bash
# Install with dev dependencies
pip install -e '.[dev]'

# Run tests
pytest

# Run single test
pytest tests/test_pipeline.py -v
```

## License

MIT
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README in English for portfolio"
```

---

## Task 9: Final Integration Test

**Step 1: Run all tests**

Run: `pytest -v`
Expected: All tests pass

**Step 2: Test web UI manually**

Run: `streamlit run app.py`
Expected:
- Auth flow works
- Can select chat after login
- Dry run shows message counts
- Full run produces downloadable markdown

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final integration and cleanup"
git push
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Add Streamlit dependency | 2 min |
| 2 | Async helper module | 5 min |
| 3 | Web auth manager | 10 min |
| 4 | Chat listing function | 5 min |
| 5 | Main Streamlit app | 15 min |
| 6 | Run script + README | 5 min |
| 7 | Docker support | 10 min |
| 8 | Portfolio README | 10 min |
| 9 | Integration test | 10 min |

**Total: ~70 minutes**
