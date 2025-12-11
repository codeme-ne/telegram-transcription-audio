from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable, Optional, Protocol

logger = logging.getLogger(__name__)

from .dry_run import DryRunReport
from .export_md import MarkdownExporter
from .filters import FilterConfig, MessageType, should_include_message
from .models import MessageEnvelope, MessageSummary, TranscriptEntry
from .state import ProcessingState


class Downloader(Protocol):
    async def download(self, message: MessageEnvelope) -> Path:
        ...


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> str:
        ...


class Writer(Protocol):
    def write(self, target: Path, content: str) -> None:
        ...


@dataclass(slots=True)
class PipelineOptions:
    dry_run: bool
    output_path: Path


@dataclass(slots=True)
class ProcessingSummary:
    processed_messages: int
    type_counts: dict[MessageType, int]
    output_path: Optional[Path]


@dataclass(slots=True)
class ProcessingPipeline:
    options: PipelineOptions
    filter_config: FilterConfig
    exporter: MarkdownExporter
    dry_run_report: DryRunReport
    downloader: Downloader
    transcriber: Transcriber
    writer: Writer
    state: ProcessingState
    self_user_id: Optional[int] = None

    async def run(self, messages: Iterable[MessageEnvelope]):
        if self.options.dry_run:
            return await self._run_dry(messages)
        return await self._run_full(messages)

    async def _run_dry(self, messages: Iterable[MessageEnvelope]):
        for message in messages:
            if self.state.has_processed(message.message_id):
                continue
            if not should_include_message(
                message, self.filter_config, self_user_id=self.self_user_id
            ):
                continue
            logger.info(
                "Processing %s %s #%s (dry-run)",
                message.date.strftime("%Y-%m-%d %H:%M"),
                message.message_type.name,
                message.message_id,
            )
            summary = MessageSummary(
                message_id=message.message_id,
                timestamp=message.date,
                sender_display=message.sender_display,
                message_type=message.message_type,
            )
            self.dry_run_report.add(summary)
        return self.dry_run_report.finalise()

    async def _run_full(self, messages: Iterable[MessageEnvelope]):
        transcript_entries: list[TranscriptEntry] = []
        counts: Counter[MessageType] = Counter()

        for message in messages:
            if self.state.has_processed(message.message_id):
                continue

            if not should_include_message(
                message, self.filter_config, self_user_id=self.self_user_id
            ):
                continue

            logger.info(
                "Processing %s %s #%s",
                message.date.strftime("%Y-%m-%d %H:%M"),
                message.message_type.name,
                message.message_id,
            )
            entry = await self._process_message(message)
            if entry is None:
                continue
            transcript_entries.append(entry)
            self.state.record_processed(message.message_id)
            counts[entry.message_type] += 1

        output_path: Optional[Path] = None

        if transcript_entries:
            markdown = self.exporter.render(transcript_entries)
            self.writer.write(self.options.output_path, markdown)
            output_path = self.options.output_path

        self.state.flush()
        return ProcessingSummary(
            processed_messages=len(transcript_entries),
            type_counts=dict(counts),
            output_path=output_path,
        )

    async def _process_message(
        self, message: MessageEnvelope
    ) -> Optional[TranscriptEntry]:
        content: Optional[str] = None

        if message.message_type is MessageType.TEXT:
            if message.text:
                content = message.text
            else:
                return None
        elif message.message_type in {
            MessageType.VOICE,
            MessageType.AUDIO,
            MessageType.VIDEO_NOTE,
        }:
            try:
                audio_path = await self.downloader.download(message)
                transcription = self.transcriber.transcribe(audio_path).strip()
                content = transcription or "[Leere Transkription]"
            except Exception as e:
                logger.warning("Transcription failed for message %s: %s", message.message_id, e)
                content = "[Transkription fehlgeschlagen]"
        else:
            return None

        return TranscriptEntry(
            message_id=message.message_id,
            timestamp=message.date,
            sender_display=message.sender_display,
            message_type=message.message_type,
            content=content,
        )
