from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_voice_transcriber.download import MediaDownloader
from telegram_voice_transcriber.filters import MessageType
from telegram_voice_transcriber.models import MessageEnvelope


class StubClient:
    def __init__(self):
        self.calls = []

    async def download_media(self, raw_message, *, file):
        self.calls.append((raw_message, file))
        path = Path(file)
        path.write_bytes(b"audio-bytes")
        return str(path)


def make_message(message_id: int, message_type: MessageType) -> MessageEnvelope:
    raw = SimpleNamespace(
        file=SimpleNamespace(ext=".ogg", mime_type="audio/ogg"),
    )
    return MessageEnvelope(
        message_id=message_id,
        sender_id=123,
        sender_display="Alice",
        date=datetime(2025, 3, 10, 9, 0, tzinfo=timezone.utc),
        message_type=message_type,
        text=None,
        raw_message=raw,
    )


@pytest.mark.asyncio
async def test_downloads_media_to_cache(tmp_path: Path):
    client = StubClient()
    downloader = MediaDownloader(client=client, base_dir=tmp_path)

    message = make_message(101, MessageType.VOICE)

    path = await downloader.download(message)

    assert path.exists()
    assert path.read_bytes() == b"audio-bytes"
    assert client.calls, "download_media should be called"
    assert path.suffix == ".ogg"
    assert path.parent.name == "03"
    assert path.parent.parent.name == "2025"


@pytest.mark.asyncio
async def test_skips_download_when_file_exists(tmp_path: Path):
    client = StubClient()
    downloader = MediaDownloader(client=client, base_dir=tmp_path)
    message = make_message(102, MessageType.VOICE)

    existing = tmp_path / "2025" / "03" / "102.ogg"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")

    path = await downloader.download(message)

    assert path == existing
    assert client.calls == []
