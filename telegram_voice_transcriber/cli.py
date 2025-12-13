from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable, List, Optional

import typer
from rich.console import Console
from rich.table import Table
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from .config import AppConfig, build_app_config, compute_date_range
from .download import MediaDownloader
from .dry_run import DryRunReport
from .export_md import MarkdownExporter
from .filters import FilterConfig, MessageType
from .models import MessageEnvelope
from .pipeline import PipelineOptions, ProcessingPipeline, ProcessingSummary
from .state import ProcessingState
from .tg_client import TelegramCollector, CollectionResult
from .transcribe import WhisperTranscriber
from .writer import FileWriter

app = typer.Typer(add_completion=False, help="Transkribiert Telegram-Sprachnachrichten in Markdown.")


@app.command()
def run(
    chat: str = typer.Argument(..., help="Name, ID oder @username des Ziel-Chats."),
    year: int = typer.Option(2025, "--year", "-y", help="Jahresfilter für Nachrichten."),
    since_date: Optional[str] = typer.Option(
        None,
        "--since-date",
        help="Startdatum (inklusive) im Format YYYY-MM-DD.",
    ),
    until_date: Optional[str] = typer.Option(
        None,
        "--until-date",
        help="Enddatum (exklusive) im Format YYYY-MM-DD.",
    ),
    count: int = typer.Option(
        None,
        "--count",
        help="Nur die letzten N Nachrichten verarbeiten (Debug/Test).",
    ),
    include_self: bool = typer.Option(
        False,
        "--include-self/--exclude-self",
        help="Auch eigene Nachrichten und Sprachnachrichten aufnehmen.",
    ),
    message_types: List[str] = typer.Option(
        ["voice", "text"],
        "--type",
        "-t",
        help="Erlaubte Nachrichtentypen (voice, audio, video_note, text). Mehrfach angeben.",
    ),
    include_ids: bool = typer.Option(
        True,
        "--include-ids/--omit-ids",
        help="Message-IDs im Markdown anzeigen.",
    ),
    timezone: str = typer.Option(
        "Europe/Vienna",
        "--timezone",
        help="Zeitzone für die Ausgabe (IANA Identifier).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Nur Vorschau anzeigen, nichts herunterladen."),
    data_dir: Path = typer.Option(
        Path(".data"),
        "--data-dir",
        help="Arbeitsverzeichnis für Cache, Markdown und Status.",
    ),
    session: Optional[Path] = typer.Option(
        None,
        "--session",
        help="Pfad zur Telegram-Session-Datei (Standard: <data-dir>/telegram.session).",
    ),
    api_id: Optional[int] = typer.Option(
        None,
        "--api-id",
        envvar="TG_API_ID",
        help="Telegram API ID (my.telegram.org).",
    ),
    api_hash: Optional[str] = typer.Option(
        None,
        "--api-hash",
        envvar="TG_API_HASH",
        help="Telegram API Hash (my.telegram.org).",
    ),
    language: str = typer.Option("de", "--language", help="Sprache für Whisper."),
    model_size: str = typer.Option(
        "small",
        "--model",
        help="Whisper-Modellgröße (z. B. tiny, base, small, medium).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose/--no-verbose",
        help="Zeige Live-Logausgabe (Processing-Zeilen) während der Verarbeitung.",
    ),
):
    """Exportiert und transkribiert einen Chat."""
    if api_id is None or api_hash is None:
        typer.secho("api-id und api-hash müssen gesetzt sein (Option oder Umgebung TG_API_ID/TG_API_HASH).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    session_path = session or (data_dir / "telegram.session")
    config = build_app_config(
        api_id=api_id,
        api_hash=api_hash,
        session_file=session_path,
        chat_identifier=chat,
        year=year,
        include_self=include_self,
        include_types=message_types,
        include_message_ids=include_ids,
        timezone_name=timezone,
        dry_run=dry_run,
        language=language,
        model_size=model_size,
        base_dir=data_dir,
        since_date=since_date,
        until_date=until_date,
    )

    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        # Etwas leiser bei Telethon
        logging.getLogger("telethon").setLevel(logging.WARNING)

    console = Console()
    try:
        asyncio.run(run_app(config, console, count=count))
    except KeyboardInterrupt:
        console.print("\n[red]Abgebrochen.[/]")
        raise typer.Exit(code=130)


async def run_app(config: AppConfig, console: Console, *, count: Optional[int] = None) -> None:
    console.print(f"[bold]Chat:[/] {config.chat_identifier} · Jahr {config.year}")

    config.paths.cache_dir.mkdir(parents=True, exist_ok=True)
    config.paths.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.state_path.parent.mkdir(parents=True, exist_ok=True)
    config.session_file.parent.mkdir(parents=True, exist_ok=True)

    async with TelegramClient(str(config.session_file), config.api_id, config.api_hash) as client:
        await ensure_authorized(client, console)

        collector = TelegramCollector(client)
        default_range = compute_date_range(config.year)
        filter_year = None if config.date_range != default_range else config.year
        collector_filter = FilterConfig(
            allowed_sender_ids=None,
            allowed_types=set(config.include_types),
            year=filter_year,
            include_self=True,
        )
        collection = await collector.collect(
            chat_identifier=config.chat_identifier,
            filter_config=collector_filter,
            since=config.date_range.since,
            until=config.date_range.until,
        )

        if not collection.messages:
            console.print("[yellow]Keine Nachrichten im angegebenen Zeitraum gefunden.[/]")
            return

        state = ProcessingState(config.paths.state_path)
        downloader = MediaDownloader(client=client, base_dir=config.paths.cache_dir)

        exporter = MarkdownExporter(
            chat_title=collection.chat_title,
            year=config.year,
            include_message_ids=config.include_message_ids,
            timezone_name=config.timezone,
        )
        dry_run_report = DryRunReport(chat_title=collection.chat_title, year=config.year)

        allowed_sender_ids = determine_sender_ids(collection, config)

        pipeline = ProcessingPipeline(
            options=PipelineOptions(
                dry_run=config.dry_run,
                output_path=config.paths.output_path,
            ),
            filter_config=FilterConfig(
                allowed_sender_ids=allowed_sender_ids,
                allowed_types=set(config.include_types),
                year=filter_year,
                include_self=config.include_self,
            ),
            exporter=exporter,
            dry_run_report=dry_run_report,
            downloader=downloader,
            transcriber=create_transcriber(config, state, collection.messages, console),
            writer=FileWriter(),
            state=state,
            self_user_id=collection.self_user_id,
        )

        messages = _limit_messages(collection.messages, count)
        if count is not None and count > 0:
            console.print(
                f"[yellow]Debug-Modus:[/] Verarbeite nur die letzten {min(count, len(collection.messages))} Nachrichten."
            )

        result = await pipeline.run(messages)
        if config.dry_run:
            print_dry_run(console, result)
        else:
            print_summary(console, result, config)


def _limit_messages(messages: Iterable[MessageEnvelope], count: Optional[int]) -> list[MessageEnvelope]:
    sequence = list(messages)
    if count is None or count <= 0:
        return sequence
    return sequence[-count:]


def determine_sender_ids(collection: CollectionResult, config: AppConfig) -> Optional[set[int]]:
    sender_ids = {
        message.sender_id for message in collection.messages if message.sender_id is not None
    }
    if collection.self_user_id is not None and not config.include_self:
        sender_ids.discard(collection.self_user_id)
    if not sender_ids:
        return None if config.include_self else set()
    return sender_ids


def create_transcriber(
    config: AppConfig,
    state: ProcessingState,
    messages,
    console: Console,
) -> WhisperTranscriber:
    needs_model = requires_transcription(config, state, messages)
    if not needs_model:
        console.print("[green]Keine neuen Audios zu transkribieren – überspringe Modell-Laden.[/]")
        return WhisperTranscriber(model=_DummyModel(), language=config.language)

    console.print("[cyan]Lade Whisper-Modell[/] "
                  f"[magenta]{config.model_size}[/] …")
    from faster_whisper import WhisperModel  # imported lazily

    models_dir = config.paths.cache_dir.parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(
        config.model_size,
        device="auto",
        compute_type="int8",
        download_root=str(models_dir),
    )
    return WhisperTranscriber(model=model, language=config.language)


def requires_transcription(
    config: AppConfig,
    state: ProcessingState,
    messages,
) -> bool:
    if config.dry_run:
        return False
    for message in messages:
        if state.has_processed(message.message_id):
            continue
        if message.message_type in {
            MessageType.VOICE,
            MessageType.AUDIO,
            MessageType.VIDEO_NOTE,
        }:
            return True
    return False


def print_dry_run(console: Console, stats) -> None:
    table = Table(title="Dry-Run Übersicht")
    table.add_column("Typ")
    table.add_column("Anzahl", justify="right")

    for message_type, count in stats.type_counts.items():
        table.add_row(message_type.value, str(count))
    table.add_row("gesamt", str(stats.total_messages), style="bold")

    console.print(table)
    if stats.example_messages:
        console.print("[bold]Beispiele:[/]")
        for summary in stats.example_messages:
            console.print(f"- {summary.render_example()}")


def print_summary(console: Console, summary: ProcessingSummary, config: AppConfig) -> None:
    table = Table(title="Verarbeitete Nachrichten")
    table.add_column("Typ")
    table.add_column("Anzahl", justify="right")
    for message_type, count in summary.type_counts.items():
        table.add_row(message_type.value, str(count))
    table.add_row("gesamt", str(summary.processed_messages), style="bold")
    console.print(table)

    if summary.output_path:
        console.print(f"[green]Markdown erzeugt:[/] {summary.output_path}")
    else:
        console.print("[yellow]Keine neuen Nachrichten verarbeitet.[/]")


async def ensure_authorized(client: TelegramClient, console: Console) -> None:
    if await client.is_user_authorized():
        return

    typer.echo("Erste Anmeldung erforderlich.")
    phone = typer.prompt("Telegram Telefonnummer (inkl. +Ländercode)")
    await client.send_code_request(phone)

    while True:
        code = typer.prompt("Bestätigungscode")
        try:
            await client.sign_in(phone=phone, code=code)
            break
        except SessionPasswordNeededError:
            password = typer.prompt("2FA Passwort", hide_input=True)
            await client.sign_in(password=password)
            break
        except PhoneCodeInvalidError:
            console.print("[red]Code ungültig, bitte erneut eingeben.[/]")
        except PhoneCodeExpiredError:
            console.print("[yellow]Code abgelaufen, fordere neuen Code an.[/]")
            await client.send_code_request(phone)


class _DummyModel:
    def transcribe(self, *args, **kwargs):
        return [], None


def main() -> None:
    app()


__all__ = ["app", "main", "run_app"]
