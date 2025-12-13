from datetime import datetime, timezone

import pytest

from telegram_voice_transcriber.filters import (
    FilterConfig,
    MessageEnvelope,
    MessageType,
    should_include_message,
)


@pytest.fixture
def alice_user():
    return 12345


@pytest.fixture
def lukasz_user():
    return 67890


def build_message(
    message_id: int,
    sender_id: int,
    *,
    year: int = 2025,
    month: int = 1,
    day: int = 1,
    hour: int = 12,
    message_type: MessageType = MessageType.VOICE,
    has_text: bool = False,
) -> MessageEnvelope:
    text = "Hallo" if has_text else None
    return MessageEnvelope(
        message_id=message_id,
        sender_id=sender_id,
        sender_display="Alice" if sender_id == 12345 else "Lukasz",
        date=datetime(year, month, day, hour, 0, tzinfo=timezone.utc),
        message_type=message_type,
        text=text,
    )


def test_includes_alice_voice_message_in_2025(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids={alice_user},
        allowed_types={MessageType.VOICE, MessageType.TEXT},
        year=2025,
        include_self=False,
    )
    message = build_message(1, alice_user, message_type=MessageType.VOICE)
    assert should_include_message(message, config, self_user_id=lukasz_user) is True


def test_excludes_messages_outside_year(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids={alice_user},
        allowed_types={MessageType.VOICE, MessageType.TEXT},
        year=2025,
        include_self=False,
    )
    message = build_message(2, alice_user, year=2024)
    assert should_include_message(message, config, self_user_id=lukasz_user) is False


def test_skips_year_filter_when_none(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids={alice_user},
        allowed_types={MessageType.VOICE, MessageType.TEXT},
        year=None,
        include_self=False,
    )
    message = build_message(2, alice_user, year=2024)
    assert should_include_message(message, config, self_user_id=lukasz_user) is True


def test_excludes_self_voice_when_not_requested(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids={alice_user},
        allowed_types={MessageType.VOICE},
        year=2025,
        include_self=False,
    )
    message = build_message(3, lukasz_user, message_type=MessageType.VOICE)
    assert should_include_message(message, config, self_user_id=lukasz_user) is False


def test_includes_self_when_flag_enabled(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids={alice_user},
        allowed_types={MessageType.VOICE},
        year=2025,
        include_self=True,
    )
    message = build_message(4, lukasz_user, message_type=MessageType.VOICE)
    assert should_include_message(message, config, self_user_id=lukasz_user) is True


def test_excludes_disallowed_type(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids={alice_user},
        allowed_types={MessageType.VOICE},
        year=2025,
        include_self=False,
    )
    message = build_message(5, alice_user, message_type=MessageType.TEXT, has_text=True)
    assert should_include_message(message, config, self_user_id=lukasz_user) is False


def test_includes_when_no_sender_restriction(alice_user, lukasz_user):
    config = FilterConfig(
        allowed_sender_ids=None,
        allowed_types={MessageType.VOICE},
        year=2025,
        include_self=False,
    )
    message = build_message(6, alice_user, message_type=MessageType.VOICE)
    assert should_include_message(message, config, self_user_id=lukasz_user) is True
