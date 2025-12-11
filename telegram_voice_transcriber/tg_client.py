from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .filters import FilterConfig, MessageType, determine_message_type
from .models import MessageEnvelope


@dataclass(slots=True)
class CollectionResult:
    chat_title: str
    self_user_id: Optional[int]
    messages: List[MessageEnvelope]


class TelegramCollector:
    def __init__(self, client: Any) -> None:
        self._client = client
        self._display_cache: Dict[int, str] = {}

    async def collect(
        self,
        chat_identifier: Any,
        filter_config: FilterConfig,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> CollectionResult:
        me = await self._client.get_me()
        self_user_id = getattr(me, "id", None)

        entity = await self._client.get_entity(chat_identifier)
        chat_title = _display_title(entity)

        messages: List[MessageEnvelope] = []
        async for message in self._client.iter_messages(
            entity,
            limit=None,
        ):
            message_date = _ensure_timezone(message.date)
            if since and message_date and message_date < since:
                break

            if until and message_date and message_date >= until:
                continue

            envelope = await self._build_envelope(
                message, filter_config.allowed_types, message_date
            )
            if envelope is None:
                continue
            messages.append(envelope)

        ordered = sorted(messages, key=lambda item: item.date)

        return CollectionResult(
            chat_title=chat_title,
            self_user_id=self_user_id,
            messages=ordered,
        )

    async def _build_envelope(
        self,
        message: Any,
        allowed_types: Iterable[MessageType],
        message_date: Optional[datetime],
    ) -> Optional[MessageEnvelope]:
        sender_id = getattr(message, "sender_id", None)
        if sender_id is None:
            sender = await message.get_sender()
            sender_id = getattr(sender, "id", None)
        if sender_id is None:
            return None

        message_type = determine_message_type(message)
        if allowed_types and message_type not in allowed_types and message_type is not MessageType.TEXT:
            # Always allow text messages for context even if not explicitly listed.
            return None

        sender_display = await self._resolve_sender_display(message, sender_id)
        text = getattr(message, "message", None)

        if message_type is MessageType.TEXT and not text:
            return None

        timestamp = message_date or datetime.now(timezone.utc)
        return MessageEnvelope(
            message_id=getattr(message, "id"),
            sender_id=sender_id,
            sender_display=sender_display,
            date=timestamp,
            message_type=message_type,
            text=text,
            raw_message=message,
        )

    async def _resolve_sender_display(self, message: Any, sender_id: int) -> str:
        if sender_id in self._display_cache:
            return self._display_cache[sender_id]

        sender = getattr(message, "sender", None)
        if sender is None:
            sender = await message.get_sender()

        display = _display_title(sender) if sender else str(sender_id)
        self._display_cache[sender_id] = display
        return display


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


def _display_title(entity: Any) -> str:
    for attr in ("title", "first_name", "username"):
        value = getattr(entity, attr, None)
        if value:
            return value
    last_name = getattr(entity, "last_name", None)
    if last_name:
        first = getattr(entity, "first_name", "")
        return f"{first} {last_name}".strip()
    return str(getattr(entity, "id", ""))


def _ensure_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
