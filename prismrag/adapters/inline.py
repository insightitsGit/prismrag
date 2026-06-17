"""PrismRAG — Inline adapter (records supplied directly in the job request)."""
from __future__ import annotations

from typing import Iterator

from prismrag.adapters.base import Record, SourceAdapter
from prismrag.models import InlineSourceConfig


class InlineAdapter(SourceAdapter):
    """Stream records from an inline list in the API request body."""

    def __init__(self, config: InlineSourceConfig):
        self._config = config

    def count_estimate(self) -> int | None:
        return len(self._config.records)

    def stream(self) -> Iterator[Record]:
        for i, rec in enumerate(self._config.records):
            word = rec.word.strip().lower()
            text = (rec.text or rec.word).strip()
            if not word:
                continue
            yield Record(
                word=word,
                text=text or word,
                ref=f"inline:{i}",
                category_hint=rec.category_hint,
            )
