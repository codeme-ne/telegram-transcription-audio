from pathlib import Path
from types import SimpleNamespace

from telegram_voice_transcriber.transcribe import WhisperTranscriber


class StubWhisperModel:
    def __init__(self):
        self.called_with = []

    def transcribe(self, audio_path, language, beam_size, best_of, condition_on_previous_text, vad_filter):
        self.called_with.append(
            dict(
                audio_path=audio_path,
                language=language,
                beam_size=beam_size,
                best_of=best_of,
                condition_on_previous_text=condition_on_previous_text,
                vad_filter=vad_filter,
            )
        )
        segments = [
            SimpleNamespace(text=" Hallo "),
            SimpleNamespace(text="Welt! "),
        ]
        return segments, None


def test_transcriber_invokes_model_with_defaults(tmp_path: Path):
    model = StubWhisperModel()
    transcriber = WhisperTranscriber(model=model, language="de", beam_size=5, best_of=5)
    audio_path = tmp_path / "audio.ogg"
    audio_path.write_bytes(b"fake")

    result = transcriber.transcribe(audio_path)

    assert result == "Hallo Welt!"
    assert model.called_with[0]["language"] == "de"
    assert model.called_with[0]["beam_size"] == 5
    assert model.called_with[0]["best_of"] == 5
    assert model.called_with[0]["condition_on_previous_text"] is False
    assert model.called_with[0]["vad_filter"] is True
