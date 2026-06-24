"""Shared store record types (mirrors prismrag/schema.sql rows)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from prismrag_patch.models import JobStatus, MappingConfig


@dataclass
class ChunkRecord:
    chunk_ref: str
    chunk_text: str
    category_slug: str
    embedding: np.ndarray
    sem_embedding: np.ndarray
    community_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    from_word: str
    to_word: str
    edge_type: str
    weight: float


@dataclass
class CommunitySummary:
    community_id: int
    label: str
    summary_text: str
    top_words: list[str]
    word_count: int
    centroid_vec: np.ndarray | None


@dataclass
class BridgeRecord:
    bridge_id: int
    community_a: int
    community_b: int
    label: str
    embedding: np.ndarray
    sem_embedding: np.ndarray


@dataclass
class JobRecord:
    job_id: str
    tenant_id: str
    status: JobStatus
    source_type: str
    mapping_id: str | None = None
    records_total: int = 0
    records_written: int = 0
    progress_pct: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
