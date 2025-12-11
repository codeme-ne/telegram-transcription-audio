from types import SimpleNamespace

from telegram_voice_transcriber.filters import MessageType, determine_message_type


def test_determine_voice_type_from_voice_flag():
    message = SimpleNamespace(
        voice=True,
        video=None,
        audio=None,
        media=None,
        message=None,
    )
    assert determine_message_type(message) == MessageType.VOICE


def test_determine_text_when_no_media():
    message = SimpleNamespace(
        voice=False,
        video=None,
        audio=None,
        media=None,
        message="Hallo Alice",
    )
    assert determine_message_type(message) == MessageType.TEXT
