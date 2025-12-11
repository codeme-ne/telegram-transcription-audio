from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WhisperTranscriber:
    model: Any
    language: str = "de"
    beam_size: int = 5
    best_of: int = 5
    vad_filter: bool = True

    def transcribe(self, audio_path: Path) -> str:
        try:
            segments, _ = self.model.transcribe(
                str(audio_path),
                language=self.language,
                beam_size=self.beam_size,
                best_of=self.best_of,
                condition_on_previous_text=False,
                vad_filter=self.vad_filter,
            )
        except Exception as e:
            logger.error("Whisper transcription failed for %s: %s", audio_path, e)
            raise

        texts = [
            getattr(segment, "text", "").strip()
            for segment in _ensure_iterable(segments)
            if getattr(segment, "text", None)
        ]
        return " ".join(text for text in texts if text).strip()


def _ensure_iterable(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return value
    return list(value)
