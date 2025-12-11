from pathlib import Path

from telegram_voice_transcriber.state import ProcessingState


def test_state_records_and_checks_ids(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state = ProcessingState(state_path=state_file)

    assert state.has_processed(42) is False

    state.record_processed(42)
    state.record_processed(43)
    state.flush()

    reloaded = ProcessingState(state_path=state_file)
    assert reloaded.has_processed(42) is True
    assert reloaded.has_processed(43) is True


def test_state_respects_max_history(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state = ProcessingState(state_path=state_file, max_history=3)

    for msg_id in range(1, 6):
        state.record_processed(msg_id)
    state.flush()

    reloaded = ProcessingState(state_path=state_file, max_history=3)
    assert reloaded.has_processed(1) is False
    assert reloaded.has_processed(3) is True
    assert reloaded.has_processed(4) is True
    assert reloaded.has_processed(6) is False
