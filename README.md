# Telegram Voice Transcriber

Export and transcribe Telegram voice messages locally using Whisper AI. **No Telegram Premium required.**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## Features

- **Privacy-first**: All processing happens locally - your data never leaves your machine
- **Smart filtering**: Filter by sender, message type, date range
- **Resumable**: Pick up where you left off with automatic state tracking
- **No Premium needed**: Uses Telegram's free API, not premium features
- **Web UI**: Simple browser interface with Streamlit
- **CLI**: Full-featured command line for automation

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
