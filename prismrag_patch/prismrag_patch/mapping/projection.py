"""Shared 768-d → 256-d projection (same algorithm as SaaS RulesStrategy)."""
from __future__ import annotations

import numpy as np

from prismrag_patch.config import EMBED_DIM_PERSONAL, EMBED_DIM_SEMANTIC

_PROJECTION: np.ndarray | None = None


def projection_matrix() -> np.ndarray:
    global _PROJECTION
    if _PROJECTION is None:
        rng = np.random.RandomState(seed=42)
        mat = rng.randn(EMBED_DIM_PERSONAL, EMBED_DIM_SEMANTIC).astype(float)
        q, _ = np.linalg.qr(mat.T)
        _PROJECTION = q.T[:EMBED_DIM_PERSONAL]
    return _PROJECTION


def project_sem_to_personal(
    sem_vec: np.ndarray,
    category_slug: str,
    categories: list[str],
) -> np.ndarray:
    """Project semantic vector into category-aware 256-d personal space."""
    cat_index = {slug: i for i, slug in enumerate(categories)}
    cat_idx = cat_index.get(category_slug, 0)
    embed_dim = EMBED_DIM_PERSONAL

    cat_signal = np.zeros(embed_dim, dtype=float)
    cat_signal[cat_idx % embed_dim] = 1.0

    sem_projected = projection_matrix() @ sem_vec
    blended = 0.30 * cat_signal + 0.70 * sem_projected
    norm = np.linalg.norm(blended)
    return (blended / norm) if norm > 0 else blended
