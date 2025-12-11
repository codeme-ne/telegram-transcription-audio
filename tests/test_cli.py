from pathlib import Path

from typer.testing import CliRunner

from telegram_voice_transcriber.cli import app


runner = CliRunner()


def test_cli_constructs_config(monkeypatch, tmp_path):
    captured = {}

    async def fake_run_app(config, console, *, count=None):
        captured["config"] = config
        captured["count"] = count

    monkeypatch.setattr("telegram_voice_transcriber.cli.run_app", fake_run_app)

    result = runner.invoke(
        app,
        [
            "Alice Example",
            "--year",
            "2025",
            "--data-dir",
            str(tmp_path / "data"),
            "--session",
            str(tmp_path / "session.session"),
            "--dry-run",
            "--count",
            "5",
        ],
        env={"TG_API_ID": "123", "TG_API_HASH": "abc"},
    )

    assert result.exit_code == 0
    config = captured["config"]
    assert config.chat_identifier == "Alice Example"
    assert config.year == 2025
    assert config.dry_run is True
    assert config.paths.output_path.name == "alice-example-2025.md"
    assert captured["count"] == 5


def test_cli_accepts_since_until(monkeypatch, tmp_path):
    captured = {}

    async def fake_run_app(config, console, *, count=None):
        captured["config"] = config
        captured["count"] = count

    monkeypatch.setattr("telegram_voice_transcriber.cli.run_app", fake_run_app)

    result = runner.invoke(
        app,
        [
            "@marianzefferer",
            "--year",
            "2025",
            "--since-date",
            "2025-02-01",
            "--until-date",
            "2025-03-01",
            "--data-dir",
            str(tmp_path / "data"),
            "--dry-run",
        ],
        env={"TG_API_ID": "123", "TG_API_HASH": "abc"},
    )

    assert result.exit_code == 0
    config = captured["config"]
    assert config.date_range.since.isoformat() == "2025-02-01T00:00:00+00:00"
    assert config.date_range.until.isoformat() == "2025-03-01T00:00:00+00:00"
    assert captured["count"] is None


def test_limit_messages_applies_count():
    from telegram_voice_transcriber.cli import _limit_messages

    messages = [1, 2, 3, 4]
    assert _limit_messages(messages, None) == [1, 2, 3, 4]
    assert _limit_messages(messages, 2) == [3, 4]
    assert _limit_messages(messages, 0) == [1, 2, 3, 4]
    assert _limit_messages(messages, -1) == [1, 2, 3, 4]


def test_cli_verbose_flag_calls_run(monkeypatch, tmp_path):
    called = {"run": False}

    async def fake_run_app(config, console, *, count=None):
        called["run"] = True

    monkeypatch.setattr("telegram_voice_transcriber.cli.run_app", fake_run_app)

    result = runner.invoke(
        app,
        [
            "@marianzefferer",
            "--year",
            "2025",
            "--since-date",
            "2025-02-01",
            "--until-date",
            "2025-03-01",
            "--data-dir",
            str(tmp_path / "data"),
            "--dry-run",
            "--verbose",
        ],
        env={"TG_API_ID": "123", "TG_API_HASH": "abc"},
    )

    assert result.exit_code == 0
    assert called["run"] is True
