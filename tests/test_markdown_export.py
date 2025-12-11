from datetime import datetime, timezone

from telegram_voice_transcriber.export_md import MarkdownExporter
from telegram_voice_transcriber.filters import MessageType
from telegram_voice_transcriber.models import TranscriptEntry


def test_markdown_export_groups_by_day():
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
    )

    entries = [
        TranscriptEntry(
            message_id=10,
            timestamp=datetime(2025, 1, 5, 8, 30, tzinfo=timezone.utc),
            sender_display="Alice",
            message_type=MessageType.TEXT,
            content="Guten Morgen!",
        ),
        TranscriptEntry(
            message_id=11,
            timestamp=datetime(2025, 1, 5, 10, 0, tzinfo=timezone.utc),
            sender_display="Alice",
            message_type=MessageType.VOICE,
            content="Bitte implementiere das Modul.",
        ),
        TranscriptEntry(
            message_id=12,
            timestamp=datetime(2025, 1, 6, 9, 15, tzinfo=timezone.utc),
            sender_display="Alice",
            message_type=MessageType.TEXT,
            content="Vergiss die Tests nicht.",
        ),
    ]

    rendered = exporter.render(entries)

    assert "# Transkript – Alice Example (2025)" in rendered
    assert "## 2025-01-05" in rendered
    assert "## 2025-01-06" in rendered
    assert "09:30 – Alice: Guten Morgen! [#ID: 10]" in rendered
    assert (
        "11:00 – Alice: Bitte implementiere das Modul. (voice) [#ID: 11]" in rendered
    )
    assert "10:15 – Alice: Vergiss die Tests nicht. [#ID: 12]" in rendered


def test_markdown_export_sanitises_markdown():
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=False,
        timezone_name="UTC",
    )
    entries = [
        TranscriptEntry(
            message_id=1,
            timestamp=datetime(2025, 2, 1, 12, 0, tzinfo=timezone.utc),
            sender_display="Alice",
            message_type=MessageType.TEXT,
            content="Bitte prüfe `code` und *Tests*.",
        )
    ]
    rendered = exporter.render(entries)
    assert "`code`" in rendered
    assert "*Tests*" in rendered
    assert "[#ID:" not in rendered
