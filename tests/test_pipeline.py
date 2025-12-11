from datetime import datetime, timezone
from pathlib import Path

import pytest

from telegram_voice_transcriber.dry_run import DryRunReport
from telegram_voice_transcriber.export_md import MarkdownExporter
from telegram_voice_transcriber.filters import FilterConfig, MessageType
from telegram_voice_transcriber.models import MessageEnvelope
from telegram_voice_transcriber.pipeline import PipelineOptions, ProcessingPipeline
from telegram_voice_transcriber.state import ProcessingState


@pytest.fixture
def alice_message():
    return MessageEnvelope(
        message_id=101,
        sender_id=123,
        sender_display="Alice",
        date=datetime(2025, 3, 10, 9, 0, tzinfo=timezone.utc),
        message_type=MessageType.VOICE,
        text=None,
    )


@pytest.fixture
def alice_text_message():
    return MessageEnvelope(
        message_id=102,
        sender_id=123,
        sender_display="Alice",
        date=datetime(2025, 3, 10, 9, 5, tzinfo=timezone.utc),
        message_type=MessageType.TEXT,
        text="Bitte die Tests anpassen.",
    )


class StubDownloader:
    def __init__(self, audio_path: Path):
        self.audio_path = audio_path
        self.called_with = []

    async def download(self, message: MessageEnvelope) -> Path:
        self.called_with.append(message.message_id)
        return self.audio_path


class StubTranscriber:
    def __init__(self, transcript: str):
        self.transcript = transcript
        self.called_paths = []

    def transcribe(self, audio_path: Path) -> str:
        self.called_paths.append(audio_path)
        return self.transcript


class MemoryWriter:
    def __init__(self) -> None:
        self.contents: str | None = None
        self.path: Path | None = None

    def write(self, target: Path, content: str) -> None:
        self.path = target
        self.contents = content


@pytest.mark.asyncio
async def test_pipeline_creates_dry_run_stats(tmp_path: Path, alice_message):
    downloader = StubDownloader(tmp_path / "audio.ogg")
    transcriber = StubTranscriber("Transkription ignoriert")
    writer = MemoryWriter()
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
    )
    dry_run_report = DryRunReport(chat_title="Alice Example", year=2025)
    state = ProcessingState(tmp_path / "state.json")

    pipeline = ProcessingPipeline(
        options=PipelineOptions(
            dry_run=True,
            output_path=tmp_path / "out.md",
        ),
        filter_config=FilterConfig(
            allowed_sender_ids={123},
            allowed_types={MessageType.VOICE, MessageType.TEXT},
            year=2025,
            include_self=False,
        ),
        exporter=exporter,
        dry_run_report=dry_run_report,
        downloader=downloader,
        transcriber=transcriber,
        writer=writer,
        state=state,
    )

    stats = await pipeline.run(iter([alice_message]))

    assert stats.total_messages == 1
    assert stats.type_counts[MessageType.VOICE] == 1
    assert downloader.called_with == []
    assert transcriber.called_paths == []
    assert writer.contents is None
    # State must remain untouched in dry-run.
    assert state.has_processed(alice_message.message_id) is False


@pytest.mark.asyncio
async def test_pipeline_dry_run_ignores_filtered_messages(tmp_path: Path, alice_message, alice_text_message):
    downloader = StubDownloader(tmp_path / "audio.ogg")
    transcriber = StubTranscriber("Ignoriert")
    writer = MemoryWriter()
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
    )
    dry_run_report = DryRunReport(chat_title="Alice Example", year=2025)
    state = ProcessingState(tmp_path / "state.json")

    pipeline = ProcessingPipeline(
        options=PipelineOptions(
            dry_run=True,
            output_path=tmp_path / "out.md",
        ),
        filter_config=FilterConfig(
            allowed_sender_ids={123},
            allowed_types={MessageType.VOICE},
            year=2025,
            include_self=False,
        ),
        exporter=exporter,
        dry_run_report=dry_run_report,
        downloader=downloader,
        transcriber=transcriber,
        writer=writer,
        state=state,
    )

    stats = await pipeline.run(iter([alice_message, alice_text_message]))

    assert stats.total_messages == 1
    assert stats.type_counts[MessageType.VOICE] == 1
    assert MessageType.TEXT not in stats.type_counts


@pytest.mark.asyncio
async def test_pipeline_processes_audio_and_text(tmp_path: Path, alice_message, alice_text_message):
    audio_path = tmp_path / "audio.ogg"
    audio_path.write_bytes(b"fake")
    downloader = StubDownloader(audio_path)
    transcriber = StubTranscriber("Bitte implementiere das Feature.")
    writer = MemoryWriter()
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
    )
    dry_run_report = DryRunReport(chat_title="Alice Example", year=2025)
    state = ProcessingState(tmp_path / "state.json")

    pipeline = ProcessingPipeline(
        options=PipelineOptions(
            dry_run=False,
            output_path=tmp_path / "out.md",
        ),
        filter_config=FilterConfig(
            allowed_sender_ids={123},
            allowed_types={MessageType.VOICE, MessageType.TEXT},
            year=2025,
            include_self=False,
        ),
        exporter=exporter,
        dry_run_report=dry_run_report,
        downloader=downloader,
        transcriber=transcriber,
        writer=writer,
        state=state,
    )

    summary = await pipeline.run(iter([alice_message, alice_text_message]))

    assert summary.processed_messages == 2
    assert summary.type_counts[MessageType.VOICE] == 1
    assert summary.type_counts[MessageType.TEXT] == 1
    assert downloader.called_with == [alice_message.message_id]
    assert transcriber.called_paths == [audio_path]
    assert writer.path == tmp_path / "out.md"
    assert "Bitte implementiere das Feature." in writer.contents
    assert "Bitte die Tests anpassen." in writer.contents
    assert state.has_processed(alice_message.message_id) is True
    assert state.has_processed(alice_text_message.message_id) is True


@pytest.mark.asyncio
async def test_pipeline_logs_each_message(tmp_path: Path, alice_message, alice_text_message, caplog):
    audio_path = tmp_path / "audio.ogg"
    audio_path.write_bytes(b"fake")
    downloader = StubDownloader(audio_path)
    transcriber = StubTranscriber("Bitte implementiere das Feature.")
    writer = MemoryWriter()
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
    )
    dry_run_report = DryRunReport(chat_title="Alice Example", year=2025)
    state = ProcessingState(tmp_path / "state.json")

    pipeline = ProcessingPipeline(
        options=PipelineOptions(
            dry_run=False,
            output_path=tmp_path / "out.md",
        ),
        filter_config=FilterConfig(
            allowed_sender_ids={123},
            allowed_types={MessageType.VOICE, MessageType.TEXT},
            year=2025,
            include_self=False,
        ),
        exporter=exporter,
        dry_run_report=dry_run_report,
        downloader=downloader,
        transcriber=transcriber,
        writer=writer,
        state=state,
    )

    caplog.set_level("INFO", logger="telegram_voice_transcriber.pipeline")

    await pipeline.run(iter([alice_message, alice_text_message]))

    text = caplog.text
    assert "Processing 2025-03-10 09:00 VOICE #101" in text
    assert "Processing 2025-03-10 09:05 TEXT #102" in text


@pytest.mark.asyncio
async def test_pipeline_skips_already_processed(tmp_path: Path, alice_message, alice_text_message):
    audio_path = tmp_path / "audio.ogg"
    audio_path.write_bytes(b"fake")
    downloader = StubDownloader(audio_path)
    transcriber = StubTranscriber("Bitte implementiere das Feature.")
    writer = MemoryWriter()
    exporter = MarkdownExporter(
        chat_title="Alice Example",
        year=2025,
        include_message_ids=True,
        timezone_name="Europe/Vienna",
    )
    dry_run_report = DryRunReport(chat_title="Alice Example", year=2025)
    state = ProcessingState(tmp_path / "state.json")
    state.record_processed(alice_message.message_id)

    pipeline = ProcessingPipeline(
        options=PipelineOptions(
            dry_run=False,
            output_path=tmp_path / "out.md",
        ),
        filter_config=FilterConfig(
            allowed_sender_ids={123},
            allowed_types={MessageType.VOICE, MessageType.TEXT},
            year=2025,
            include_self=False,
        ),
        exporter=exporter,
        dry_run_report=dry_run_report,
        downloader=downloader,
        transcriber=transcriber,
        writer=writer,
        state=state,
    )

    summary = await pipeline.run(iter([alice_message, alice_text_message]))

    assert summary.processed_messages == 1
    assert MessageType.VOICE not in summary.type_counts
    assert summary.type_counts[MessageType.TEXT] == 1
