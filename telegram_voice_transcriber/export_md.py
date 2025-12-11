from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from dateutil.tz import gettz

from .filters import MessageType
from .models import TranscriptEntry


@dataclass(slots=True)
class MarkdownExporter:
    chat_title: str
    year: int
    include_message_ids: bool
    timezone_name: str

    def render(self, entries: Iterable[TranscriptEntry]) -> str:
        tzinfo = gettz(self.timezone_name)
        sorted_entries = sorted(entries, key=lambda item: item.timestamp)

        grouped: dict[str, List[TranscriptEntry]] = defaultdict(list)
        for entry in sorted_entries:
            localized = entry.timestamp.astimezone(tzinfo)
            date_key = localized.strftime("%Y-%m-%d")
            grouped[date_key].append(
                TranscriptEntry(
                    message_id=entry.message_id,
                    timestamp=localized,
                    sender_display=entry.sender_display,
                    message_type=entry.message_type,
                    content=entry.content,
                )
            )

        lines: List[str] = [f"# Transkript – {self.chat_title} ({self.year})"]

        for date_key in sorted(grouped.keys()):
            lines.append("")
            lines.append(f"## {date_key}")
            for entry in grouped[date_key]:
                time_str = entry.timestamp.strftime("%H:%M")
                suffix = self._type_suffix(entry.message_type)
                content = entry.content.strip()
                id_suffix = (
                    f" [#ID: {entry.message_id}]"
                    if self.include_message_ids
                    else ""
                )
                lines.append(
                    f"{time_str} – {entry.sender_display}: {content}{suffix}{id_suffix}"
                )

        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _type_suffix(message_type: MessageType) -> str:
        if message_type is MessageType.TEXT:
            return ""
        return f" ({message_type.value})"
