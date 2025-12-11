from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Set

from .filters import MessageType


@dataclass(slots=True)
class PathConfig:
    cache_dir: Path
    output_path: Path
    state_path: Path


@dataclass(slots=True)
class DateRange:
    since: datetime
    until: datetime


@dataclass(slots=True)
class AppConfig:
    chat_identifier: str
    chat_slug: str
    year: int
    include_self: bool
    include_types: Set[MessageType]
    include_message_ids: bool
    timezone: str
    dry_run: bool
    language: str
    model_size: str
    api_id: int
    api_hash: str
    session_file: Path
    paths: PathConfig
    date_range: DateRange


def slugify_chat_name(name: str) -> str:
    lowered = name.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "chat"


def parse_message_types(values: Iterable[str]) -> Set[MessageType]:
    types = set()
    for value in values:
        try:
            types.add(MessageType(value))
        except ValueError as exc:
            raise ValueError(f"Unbekannter Nachrichtentyp: {value}") from exc
    return types


def compute_paths(base_dir: Path, chat_slug: str, year: int) -> PathConfig:
    year_dir = base_dir / chat_slug / str(year)
    cache_dir = year_dir / "cache"
    output_dir = year_dir / "output"
    output_path = output_dir / f"{chat_slug}-{year}.md"
    state_path = year_dir / "state" / "state.json"
    return PathConfig(
        cache_dir=cache_dir,
        output_path=output_path,
        state_path=state_path,
    )


def compute_date_range(year: int) -> DateRange:
    since = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    until = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return DateRange(since=since, until=until)


def build_app_config(
    *,
    api_id: int,
    api_hash: str,
    session_file: Path,
    chat_identifier: str,
    year: int,
    include_self: bool,
    include_types: Iterable[str],
    include_message_ids: bool,
    timezone_name: str,
    dry_run: bool,
    language: str,
    model_size: str,
    base_dir: Path,
    since_date: str | None = None,
    until_date: str | None = None,
) -> AppConfig:
    chat_slug = slugify_chat_name(chat_identifier)
    types = parse_message_types(include_types)
    paths = compute_paths(base_dir, chat_slug, year)
    date_range = _resolve_date_range(year, since_date, until_date)

    return AppConfig(
        chat_identifier=chat_identifier,
        chat_slug=chat_slug,
        year=year,
        include_self=include_self,
        include_types=types,
        include_message_ids=include_message_ids,
        timezone=timezone_name,
        dry_run=dry_run,
        language=language,
        model_size=model_size,
        api_id=api_id,
        api_hash=api_hash,
        session_file=session_file,
        paths=paths,
        date_range=date_range,
    )


def _resolve_date_range(
    year: int,
    since_date: str | None,
    until_date: str | None,
) -> DateRange:
    if since_date is None and until_date is None:
        return compute_date_range(year)

    if not since_date or not until_date:
        raise ValueError("both --since-date and --until-date must be provided together")

    since = _parse_date(since_date)
    until = _parse_date(until_date)

    if since >= until:
        raise ValueError("since-date must be earlier than until-date")

    return DateRange(since=since, until=until)


def _parse_date(value: str) -> datetime:
    try:
        naive = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Ungültiges Datum: {value}") from exc
    return naive.replace(tzinfo=timezone.utc)
