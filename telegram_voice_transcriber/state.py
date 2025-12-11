from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Set


@dataclass
class ProcessingState:
    state_path: Path
    max_history: int = 2000
    _ordered_ids: Deque[int] = field(init=False, repr=False, default_factory=deque)
    _id_index: Set[int] = field(init=False, repr=False, default_factory=set)
    _dirty: bool = field(init=False, repr=False, default=False)

    def __post_init__(self) -> None:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                ids = data.get("processed_ids", [])
                for message_id in ids[-self.max_history :]:
                    if isinstance(message_id, int):
                        self._ordered_ids.append(message_id)
                        self._id_index.add(message_id)
            except (json.JSONDecodeError, OSError):
                # Start fresh if the state is unreadable.
                self._ordered_ids = deque()
                self._id_index = set()

    def has_processed(self, message_id: int) -> bool:
        return message_id in self._id_index

    def record_processed(self, message_id: int) -> None:
        if message_id in self._id_index:
            return
        self._ordered_ids.append(message_id)
        self._id_index.add(message_id)
        self._dirty = True
        self._trim()

    def _trim(self) -> None:
        excess = len(self._ordered_ids) - self.max_history
        if excess <= 0:
            return
        for _ in range(excess):
            oldest = self._ordered_ids.popleft()
            self._id_index.discard(oldest)

    def flush(self) -> None:
        if not self._dirty:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"processed_ids": list(self._ordered_ids)[-self.max_history :]}
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(self.state_path)
        self._dirty = False
