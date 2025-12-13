from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Optional, Protocol


class MessageLike(Protocol):
    """Protocol describing attributes we inspect on Telethon messages."""

    id: int
    date: datetime
    peer_id: object | None
    sender_id: int | None
    message: str | None


class MessageType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    AUDIO = "audio"
    VIDEO_NOTE = "video_note"
    OTHER = "other"


@dataclass(frozen=True)
class FilterConfig:
    allowed_sender_ids: Optional[set[int]]
    allowed_types: set[MessageType]
    year: Optional[int]
    include_self: bool


def determine_message_type(message: object) -> MessageType:
    """Infer message type using a subset of Telethon attributes."""
    # Voice notes expose `voice=True`.
    voice_flag = getattr(message, "voice", False)
    if voice_flag:
        return MessageType.VOICE

    # Video notes are `video_note` or round videos (document attribute).
    if getattr(message, "video", None) and getattr(message, "round", False):
        return MessageType.VIDEO_NOTE

    if getattr(message, "video_note", False):
        return MessageType.VIDEO_NOTE

    # Plain audio files.
    if getattr(message, "audio", None):
        return MessageType.AUDIO

    if getattr(message, "message", None):
        return MessageType.TEXT

    return MessageType.OTHER


def should_include_message(
    message: "MessageEnvelope",
    config: FilterConfig,
    *,
    self_user_id: Optional[int],
) -> bool:
    """Check if message passes sender/type/year filters."""
    if message.message_type not in config.allowed_types:
        return False

    # When year is None we skip the year-based filter (used for date-range mode).
    if config.year is not None and not within_year(message.date, config.year):
        return False

    if message.sender_id == self_user_id:
        return config.include_self

    if config.allowed_sender_ids is None:
        return True

    return message.sender_id in config.allowed_sender_ids


def within_year(timestamp: datetime, year: int) -> bool:
    return timestamp.year == year


# Circular imports guard (MessageEnvelope defined in models.py)
from .models import MessageEnvelope  # noqa: E402  # isort:skip
