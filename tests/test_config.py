import pytest

from pathlib import Path

from telegram_voice_transcriber.config import (
    build_app_config,
    parse_message_types,
    slugify_chat_name,
)
from telegram_voice_transcriber.filters import MessageType


def test_slugify_chat_name():
    assert slugify_chat_name("Alice Example") == "alice-example"
    assert slugify_chat_name("Chat_with@Alice!") == "chat-with-alice"


def test_parse_message_types_accepts_known_values():
    result = parse_message_types(["voice", "text"])
    assert result == {MessageType.VOICE, MessageType.TEXT}


def test_parse_message_types_rejects_unknown_value():
    with pytest.raises(ValueError):
        parse_message_types(["voice", "unknown"])


def test_build_app_config_sets_paths(tmp_path: Path):
    cfg = build_app_config(
        api_id=1,
        api_hash="hash",
        session_file=tmp_path / "session.session",
        chat_identifier="Alice Example",
        year=2025,
        include_self=False,
        include_types=["voice", "text"],
        include_message_ids=True,
        timezone_name="Europe/Vienna",
        dry_run=False,
        language="de",
        model_size="small",
        base_dir=tmp_path / "data",
    )

    assert cfg.chat_slug == "alice-example"
    assert cfg.paths.output_path.name == "alice-example-2025.md"
