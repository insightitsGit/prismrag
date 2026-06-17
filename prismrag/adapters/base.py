"""PrismRAG — Source adapter base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class Record:
    """A single chunk record yielded by a source adapter."""
    __slots__ = ("word", "text", "ref", "category_hint", "metadata")

    def __init__(
        self,
        word: str,
        text: str,
        ref: str = "",
        category_hint: str | None = None,
        metadata: dict | None = None,
    ):
        self.word          = word.strip().lower()
        self.text          = text
        self.ref           = ref
        self.category_hint = category_hint   # pre-assigned category (optional)
        self.metadata      = metadata or {}


class SourceAdapter(ABC):
    """All source adapters implement this interface."""

    @abstractmethod
    def stream(self) -> Iterator[Record]:
        """Yield records one at a time. Memory-safe for large sources."""

    def count_estimate(self) -> int | None:
        """Return approximate record count, or None if unknown."""
        return None

    def close(self) -> None:
        """Release any held resources."""
