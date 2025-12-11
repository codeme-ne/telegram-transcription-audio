from datetime import datetime, timezone

from telegram_voice_transcriber.dry_run import DryRunReport
from telegram_voice_transcriber.filters import MessageType
from telegram_voice_transcriber.models import MessageSummary


def test_dry_run_counts_messages():
    report = DryRunReport(chat_title="Alice Example", year=2025)

    report.add(
        MessageSummary(
            message_id=1,
            timestamp=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
            sender_display="Alice",
            message_type=MessageType.VOICE,
        )
    )
    report.add(
        MessageSummary(
            message_id=2,
            timestamp=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            sender_display="Alice",
            message_type=MessageType.TEXT,
        )
    )

    stats = report.finalise()

    assert stats.total_messages == 2
    assert stats.type_counts[MessageType.VOICE] == 1
    assert stats.type_counts[MessageType.TEXT] == 1
    assert len(stats.example_messages) == 2
