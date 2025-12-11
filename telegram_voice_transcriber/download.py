from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .filters import MessageType
from .models import MessageEnvelope


class MediaDownloader:
    """Download Telegram media into a deterministic cache structure."""

    def __init__(self, client: Any, base_dir: Path) -> None:
        self._client = client
        self._base_dir = base_dir

    async def download(self, message: MessageEnvelope) -> Path:
        if message.raw_message is None:
            raise ValueError("Cannot download media without original message object.")

        ext = _infer_extension(message)
        timestamp = _ensure_timestamp(message.date)
        target_dir = self._base_dir / f"{timestamp.year}" / f"{timestamp.month:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / f"{message.message_id}{ext}"
        if target_path.exists():
            return target_path

        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        result_path = await self._client.download_media(
            message.raw_message,
            file=str(tmp_path),
        )

        final_path = Path(result_path)
        if final_path != target_path:
            if final_path.exists():
                final_path.replace(target_path)
            else:
                tmp_path.replace(target_path)
        elif tmp_path.exists():
            tmp_path.replace(target_path)

        return target_path


def _infer_extension(message: MessageEnvelope) -> str:
    raw = message.raw_message
    extensions = [
        getattr(getattr(raw, "file", None), "ext", None),
        getattr(getattr(raw, "document", None), "ext", None),
    ]
    for ext in extensions:
        if ext:
            return ext if ext.startswith(".") else f".{ext}"

    mime = getattr(getattr(raw, "file", None), "mime_type", None)
    if mime == "audio/ogg":
        return ".ogg"
    if mime == "audio/mpeg":
        return ".mp3"
    if mime == "video/mp4":
        return ".mp4"

    defaults = {
        MessageType.VOICE: ".ogg",
        MessageType.AUDIO: ".mp3",
        MessageType.VIDEO_NOTE: ".mp4",
    }
    return defaults.get(message.message_type, ".bin")


def _ensure_timestamp(date: Optional[datetime]) -> datetime:
    if date is None:
        return datetime.now(timezone.utc)
    if date.tzinfo is None:
        return date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)
