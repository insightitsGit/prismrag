"""PrismRAG library — lightweight data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class SourceType(str, Enum):
    inline = "inline"
    file = "file"
    sql = "sql"
    api = "api"
    chunk = "chunk"


@dataclass
class InlineRecord:
    word: str
    text: str | None = None
    category_hint: str | None = None


@dataclass
class MappingConfig:
    categories: list[dict[str, Any]]
    rules: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MappingConfig":
        return cls(categories=list(d.get("categories", [])), rules=list(d.get("rules", [])))


@dataclass
class ChunkIn:
    ref: str
    text: str


@dataclass
class RuleIn:
    word: str
    category_slug: str
    weight: float = 1.0


@dataclass
class AppendRequest:
    chunks: list[ChunkIn]
    new_rules: list[RuleIn] = field(default_factory=list)
    ml_fallback: str = "auto"
    include_vectors: bool = False


@dataclass
class AppendChunkResult:
    chunk_ref: str
    chunk_text: str
    category_slug: str
    confidence: float
    separation: float
    coherence: float
    quality_score: float
    flagged: bool
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "chunk_ref": self.chunk_ref,
            "chunk_text": self.chunk_text,
            "category_slug": self.category_slug,
            "confidence": self.confidence,
            "separation": self.separation,
            "coherence": self.coherence,
            "quality_score": self.quality_score,
            "flagged": self.flagged,
        }
        if self.embedding is not None:
            out["embedding"] = self.embedding
        return out
