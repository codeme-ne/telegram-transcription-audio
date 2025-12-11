from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from .filters import MessageType
from .models import DryRunStats, MessageSummary


@dataclass
class DryRunReport:
    chat_title: str
    year: int
    sample_size: int = 5
    _total: int = field(init=False, default=0)
    _type_counter: Counter[MessageType] = field(
        init=False, default_factory=Counter
    )
    _examples: List[MessageSummary] = field(init=False, default_factory=list)

    def add(self, summary: MessageSummary) -> None:
        self._total += 1
        self._type_counter[summary.message_type] += 1
        if len(self._examples) < self.sample_size:
            self._examples.append(summary)

    def finalise(self) -> DryRunStats:
        return DryRunStats(
            chat_title=self.chat_title,
            year=self.year,
            total_messages=self._total,
            type_counts=dict(self._type_counter),
            example_messages=self._examples,
        )
