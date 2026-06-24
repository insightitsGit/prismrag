"""Chunk quality scoring (parity with SaaS prismrag.pipeline.quality)."""
from __future__ import annotations

from typing import NamedTuple

import numpy as np

from prismrag_patch.config import LOW_QUALITY_THRESHOLD


class ChunkQuality(NamedTuple):
    chunk_ref: str
    confidence: float
    separation: float
    coherence: float
    quality_score: float
    flagged: bool


def score_batch(
    chunk_refs: list[str],
    embeddings: np.ndarray,
    category_slugs: list[str],
    confidences: list[float] | None = None,
) -> list[ChunkQuality]:
    n = len(chunk_refs)
    if n == 0:
        return []

    embs = np.asarray(embeddings, dtype=float)
    norms = np.linalg.norm(embs, axis=1, keepdims=True).clip(min=1e-8)
    embs_n = embs / norms

    cats_unique = list(dict.fromkeys(category_slugs))
    centroids: dict[str, np.ndarray] = {}
    for c in cats_unique:
        mask = [i for i, s in enumerate(category_slugs) if s == c]
        cent = embs_n[mask].mean(axis=0)
        norm_c = np.linalg.norm(cent)
        centroids[c] = cent / norm_c if norm_c > 1e-8 else cent

    scores: list[ChunkQuality] = []
    for i in range(n):
        vec = embs_n[i]
        assigned = category_slugs[i]

        if confidences is not None:
            conf = float(np.clip(confidences[i], 0.0, 1.0))
        else:
            cent = centroids.get(assigned, np.zeros_like(vec))
            conf = float(np.clip(vec @ cent, 0.0, 1.0))

        sims = {c: float(vec @ centroids[c]) for c in cats_unique}
        sim_best = sims[assigned]
        others = [v for c, v in sims.items() if c != assigned]
        separation = float(np.clip((sim_best - max(others) + 1.0) / 2.0, 0.0, 1.0)) if others else 1.0

        peers = [j for j, s in enumerate(category_slugs) if s == assigned and j != i]
        if peers:
            peer_sims = embs_n[peers] @ vec
            top_k = min(5, len(peers))
            coherence = float(np.clip(np.partition(peer_sims, -top_k)[-top_k:].mean(), 0.0, 1.0))
        else:
            coherence = 1.0

        quality = 0.40 * conf + 0.40 * separation + 0.20 * coherence
        scores.append(ChunkQuality(
            chunk_ref=chunk_refs[i],
            confidence=round(conf, 4),
            separation=round(separation, 4),
            coherence=round(coherence, 4),
            quality_score=round(quality, 4),
            flagged=quality < LOW_QUALITY_THRESHOLD,
        ))
    return scores


def summarise_quality(scores: list[dict]) -> dict:
    if not scores:
        return {"total": 0, "flagged": 0, "avg_quality": None}

    qs = [s["quality_score"] for s in scores]
    summary: dict = {
        "total": len(scores),
        "flagged": sum(1 for s in scores if s.get("flagged", False)),
        "pct_flagged": round(100 * sum(1 for s in scores if s.get("flagged", False)) / len(scores), 1),
        "avg_quality": round(float(np.mean(qs)), 4),
        "min_quality": round(float(np.min(qs)), 4),
        "p25_quality": round(float(np.percentile(qs, 25)), 4),
        "p50_quality": round(float(np.percentile(qs, 50)), 4),
        "p75_quality": round(float(np.percentile(qs, 75)), 4),
    }
    conf_vals = [s["confidence"] for s in scores if "confidence" in s]
    if conf_vals:
        summary["avg_confidence"] = round(float(np.mean(conf_vals)), 4)
    return summary
