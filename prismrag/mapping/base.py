"""PrismRAG — Mapping strategy base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class MappingResult:
    """Output of a mapping strategy for one record."""
    category_slug: str          # assigned category (from Tier-1 rules)
    embedding: np.ndarray       # 256-d personal vector
    sem_embedding: np.ndarray | None = None  # 768-d Gemini vector (kept for centroid search)


class MappingStrategy(ABC):
    """
    Given a word + text, produce:
      - a category assignment (Tier 1)
      - a personal embedding vector (Tier 1 or 2)
    """

    @abstractmethod
    def assign(self, word: str, text: str, category_hint: str | None = None) -> MappingResult:
        """Assign a category and produce a vector for one record."""

    def assign_batch(
        self, records: list[tuple[str, str, str | None]]
    ) -> list[MappingResult]:
        """
        Batch assign. Default: calls assign() per record.
        Override for strategies that benefit from batching (e.g. MLP).
        records: list of (word, text, category_hint)
        """
        return [self.assign(w, t, h) for w, t, h in records]

    def close(self) -> None:
        """Release resources (e.g. model weights). Optional."""
