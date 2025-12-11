from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Sequence

from .filters import MessageType


@dataclass(slots=True)
class MessageEnvelope:
    """Lightweight view of a Telegram message relevant for filtering."""

    message_id: int
    sender_id: int
    sender_display: str
    date: datetime
    message_type: MessageType
    text: str | None = None
    raw_message: Any | None = None


@dataclass(slots=True)
class TranscriptEntry:
    """A single line (text or transcribed audio) going into the Markdown export."""

    message_id: int
    timestamp: datetime
    sender_display: str
    message_type: MessageType
    content: str


@dataclass(slots=True)
class MessageSummary:
    """Compact summary used for dry-run previews."""

    message_id: int
    timestamp: datetime
    sender_display: str
    message_type: MessageType

    def render_example(self) -> str:
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return f"{time_str} – {self.sender_display} ({self.message_type.value})"


@dataclass(slots=True)
class DryRunStats:
    """Aggregated dry-run information reported to the user."""

    chat_title: str
    year: int
    total_messages: int
    type_counts: Dict[MessageType, int]
    example_messages: Sequence[MessageSummary] = field(default_factory=list)
