from __future__ import annotations

from pathlib import Path


class FileWriter:
    """Writes rendered Markdown to disk."""

    def write(self, target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
