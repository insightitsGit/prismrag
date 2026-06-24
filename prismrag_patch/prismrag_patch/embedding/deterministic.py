"""Deterministic embeddings for offline tests (no API key required)."""
from __future__ import annotations

import hashlib
from typing import Callable

import numpy as np

from prismrag_patch.config import EMBED_DIM_SEMANTIC


def _hash_to_vec(text: str, dim: int = EMBED_DIM_SEMANTIC) -> np.ndarray:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.RandomState(int.from_bytes(digest[:4], "big"))
    v = rng.randn(dim).astype(float)
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def embed_text(text: str) -> list[float]:
    return _hash_to_vec(text).tolist()


def embed_texts(texts: list[str]) -> list[list[float] | None]:
    return [embed_text(t) for t in texts]


def make_embed_fn(dim: int = EMBED_DIM_SEMANTIC) -> Callable[[list[str]], list[list[float] | None]]:
    def _fn(texts: list[str]) -> list[list[float] | None]:
        return [_hash_to_vec(t, dim).tolist() for t in texts]

    return _fn
