import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from telegram_voice_transcriber.filters import FilterConfig, MessageType
from telegram_voice_transcriber.models import MessageEnvelope
from telegram_voice_transcriber.tg_client import TelegramCollector


class FakeMessage:
    def __init__(self, message_id, sender_id, text=None, voice=False, date=None):
        self.id = message_id
        self.sender_id = sender_id
        self.message = text
        self.voice = voice
        self.video = None
        self.round = False
        self.video_note = False
        self.audio = None
        self.date = date or datetime(2025, 1, 1, tzinfo=timezone.utc)

    async def get_sender(self):
        return SimpleNamespace(id=self.sender_id, first_name="Alice", last_name=None)


class FakeClient:
    def __init__(self, messages):
        self._messages = messages

    async def get_me(self):
        return SimpleNamespace(id=67890, first_name="Lukasz")

    async def get_entity(self, chat_identifier):
        return SimpleNamespace(id=12345, title="Alice Example")

    def iter_messages(self, entity, limit=None, reverse=False, offset_date=None):
        async def generator():
            for message in reversed(self._messages):
                yield message

        return generator()


@pytest.mark.asyncio
async def test_collector_builds_envelopes():
    messages = [
        FakeMessage(1, 12345, text="Hallo", date=datetime(2025, 1, 2, tzinfo=timezone.utc)),
        FakeMessage(2, 12345, voice=True, date=datetime(2025, 1, 3, tzinfo=timezone.utc)),
    ]
    client = FakeClient(messages)
    collector = TelegramCollector(client)
    filter_config = FilterConfig(
        allowed_sender_ids={12345},
        allowed_types={MessageType.TEXT, MessageType.VOICE},
        year=2025,
        include_self=False,
    )

    result = await collector.collect(
        chat_identifier="Alice Example",
        filter_config=filter_config,
        since=datetime(2025, 1, 1, tzinfo=timezone.utc),
        until=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )

    assert result.self_user_id == 67890
    assert result.chat_title == "Alice Example"
    assert isinstance(result.messages, list)
    assert len(result.messages) == 2
    assert all(isinstance(msg, MessageEnvelope) for msg in result.messages)

    voice_message = next(msg for msg in result.messages if msg.message_id == 2)
    assert voice_message.message_type is MessageType.VOICE
    assert voice_message.sender_display == "Alice"


@pytest.mark.asyncio
async def test_collector_filters_within_dates():
    messages = [
        FakeMessage(1, 12345, text="Alt", date=datetime(2025, 1, 31, tzinfo=timezone.utc)),
        FakeMessage(2, 12345, text="Innen", date=datetime(2025, 2, 1, 9, 0, tzinfo=timezone.utc)),
        FakeMessage(3, 12345, text="Nach", date=datetime(2025, 3, 1, tzinfo=timezone.utc)),
    ]
    client = FakeClient(messages)
    collector = TelegramCollector(client)
    filter_config = FilterConfig(
        allowed_sender_ids={12345},
        allowed_types={MessageType.TEXT},
        year=2025,
        include_self=False,
    )

    result = await collector.collect(
        chat_identifier="Alice Example",
        filter_config=filter_config,
        since=datetime(2025, 2, 1, tzinfo=timezone.utc),
        until=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )

    assert [msg.message_id for msg in result.messages] == [2]


@pytest.mark.asyncio
async def test_list_dialogs_returns_chat_list():
    from unittest.mock import MagicMock

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

    async def mock_iter_dialogs(limit=None):
        for d in [mock_dialog1, mock_dialog2]:
            yield d

    mock_client.iter_dialogs = mock_iter_dialogs

    from telegram_voice_transcriber.tg_client import list_dialogs
    dialogs = await list_dialogs(mock_client)

    assert len(dialogs) == 2
    assert dialogs[0]["name"] == "Alice"
    assert dialogs[0]["id"] == 123
    assert dialogs[1]["name"] == "Work Group"
