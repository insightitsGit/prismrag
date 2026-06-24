"""PrismRAG library — mapping strategy base."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class MappingResult:
    category_slug: str
    embedding: np.ndarray
    sem_embedding: np.ndarray | None = None


class MappingStrategy(ABC):
    @abstractmethod
    def assign(self, word: str, text: str, category_hint: str | None = None) -> MappingResult:
        ...

    def assign_batch(
        self, records: list[tuple[str, str, str | None]]
    ) -> list[MappingResult]:
        return [self.assign(w, t, h) for w, t, h in records]

    def close(self) -> None:
        pass
