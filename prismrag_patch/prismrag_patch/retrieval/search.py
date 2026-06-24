"""Graph RAG retrieval (parity with SaaS prismrag.retrieval.search)."""
from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np

from prismrag_patch.config import (
    BFS_MAX_HOPS,
    BFS_MAX_WORDS,
    RETRIEVAL_TOP_COMMUNITIES,
    RETRIEVAL_TOP_K,
)
from prismrag_patch.store.memory import MemoryStore
from prismrag_patch.store.postgres import PostgresStore
from prismrag_patch.store.types import ChunkRecord

logger = logging.getLogger(__name__)


def retrieve(
    store: MemoryStore | PostgresStore,
    tenant_id: str,
    query: str,
    embed_fn: Callable[[list[str]], list[list[float] | None]],
    mapping_id: str | None = None,
    top_k: int = RETRIEVAL_TOP_K,
    category_filter: str | None = None,
    model: Any | None = None,
) -> dict[str, Any]:
    if not mapping_id:
        mapping_id = store.latest_mapping(tenant_id)
    if not mapping_id:
        return _empty(tenant_id, query, "")

    query_tokens = [t for t in query.lower().split() if len(t) > 1]
    vecs = embed_fn(query_tokens or [query])
    valid = [np.array(v, dtype=float) for v in vecs if v is not None]
    if not valid:
        return _empty(tenant_id, query, mapping_id)

    query_sem = np.mean(valid, axis=0)
    norm = np.linalg.norm(query_sem)
    if norm > 0:
        query_sem /= norm

    communities_raw = store.list_communities(tenant_id, mapping_id)
    communities = [
        {
            "community_id": c.community_id,
            "label": c.label,
            "summary_text": c.summary_text,
            "top_words": c.top_words,
            "word_count": c.word_count,
            "centroid_vec": c.centroid_vec,
        }
        for c in communities_raw
    ]

    hits: list[dict] = []
    community_context: list[dict] = []
    mode = "direct"

    if communities:
        try:
            hits, community_context = _graph_retrieve(
                store, tenant_id, mapping_id, query_sem, query_tokens,
                communities, model, top_k, category_filter, embed_fn,
            )
            mode = "graph_rag"
        except Exception as exc:
            logger.warning("Graph RAG failed, falling back to direct: %s", exc)

    if not hits:
        hits = _direct_retrieve(store, tenant_id, mapping_id, query_sem, top_k, category_filter)
        mode = "direct"

    return {
        "query": query,
        "tenant_id": tenant_id,
        "mapping_id": mapping_id,
        "retrieval_mode": mode,
        "hits": hits,
        "results": hits,
        "communities": community_context,
    }


def _graph_retrieve(
    store, tenant_id, mapping_id, query_sem, query_tokens,
    communities, model, top_k, category_filter, embed_fn,
):
    ranked_comms = _rank_communities(query_sem, communities)
    seed_words: list[str] = []
    for cid, _ in ranked_comms[:RETRIEVAL_TOP_COMMUNITIES]:
        comm = next((c for c in communities if c["community_id"] == cid), None)
        if comm:
            seed_words.extend(comm.get("top_words") or [])
    seed_words.extend(query_tokens)
    seed_words = list(dict.fromkeys(seed_words))

    expanded = _bfs_expand(store, tenant_id, mapping_id, seed_words)
    candidates = list(dict.fromkeys(seed_words + expanded))
    chunks = store.list_chunks(tenant_id, mapping_id, refs=candidates, category_filter=category_filter)
    if not chunks:
        return [], []

    if model:
        chunks = _mlp_rerank(model, query_tokens, chunks, top_k, embed_fn)
    else:
        chunks = _sem_rerank(query_sem, chunks, top_k)

    hits = [_to_hit(c, communities) for c in chunks]
    community_context = [
        {
            "communityId": cid,
            "weight": float(w),
            "label": next((c["label"] for c in communities if c["community_id"] == cid), ""),
            "summary": next((c["summary_text"] for c in communities if c["community_id"] == cid), ""),
        }
        for cid, w in ranked_comms[:3]
    ]
    return hits, community_context


def _rank_communities(query_sem: np.ndarray, communities: list[dict]) -> list[tuple[int, float]]:
    scored: list[tuple[int, float]] = []
    for c in communities:
        centroid = c.get("centroid_vec")
        if centroid is None:
            continue
        cv = np.array(centroid, dtype=float)
        cn = np.linalg.norm(cv)
        if cn > 0:
            cv = cv / cn
        sim = float(query_sem @ cv)
        scored.append((c["community_id"], sim))

    if not scored:
        return []

    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:RETRIEVAL_TOP_COMMUNITIES]
    vals = np.array([s for _, s in scored])
    vals = vals - vals.max()
    weights = np.exp(vals)
    weights /= weights.sum()
    return [(int(cid), float(w)) for (cid, _), w in zip(scored, weights)]


def _bfs_expand(store: MemoryStore | PostgresStore, tenant_id: str, mapping_id: str, seed_words: list[str]) -> list[str]:
    if not seed_words:
        return []
    edges = store.get_edges(tenant_id, mapping_id)
    visited = set(seed_words)
    frontier = list(seed_words)

    for _ in range(BFS_MAX_HOPS):
        if not frontier or len(visited) >= BFS_MAX_WORDS:
            break
        new: list[str] = []
        for e in edges:
            if e.from_word in frontier and e.to_word not in visited:
                new.append(e.to_word)
            if e.to_word in frontier and e.from_word not in visited:
                new.append(e.from_word)
        new = [w for w in new if w not in visited]
        if not new:
            break
        batch = new[: max(0, BFS_MAX_WORDS - len(visited))]
        visited.update(batch)
        frontier = batch

    return list(visited)


def _sem_rerank(query_sem: np.ndarray, chunks: list[ChunkRecord], top_k: int) -> list[ChunkRecord]:
    scored: list[tuple[ChunkRecord, float]] = []
    for rec in chunks:
        vec = rec.sem_embedding.copy()
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        scored.append((rec, float(vec @ query_sem)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scored[:top_k]]


def _mlp_rerank(model, query_tokens, chunks, top_k, embed_fn):
    try:
        import torch
        token_texts = query_tokens or ["query"]
        token_arr = np.array([v for v in embed_fn(token_texts) if v is not None], dtype=float)
        if token_arr.shape[0] == 0:
            return chunks[:top_k]
        with torch.no_grad():
            t_in = torch.tensor(token_arr, dtype=torch.float32)
            t_out = model(t_in).numpy()
        scored = []
        for rec in chunks:
            sim = float((rec.embedding @ t_out.T).max())
            scored.append((rec, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]
    except Exception:
        return chunks[:top_k]


def _to_hit(rec: ChunkRecord, communities: list[dict]) -> dict:
    comm_label = next(
        (c["label"] for c in communities if c["community_id"] == rec.community_id), None
    )
    return {
        "chunk_text": rec.chunk_text,
        "chunk_ref": rec.chunk_ref,
        "category_slug": rec.category_slug,
        "community_id": rec.community_id,
        "community_label": comm_label,
        "score": 0.0,
        "metadata": rec.metadata,
    }


def _direct_retrieve(
    store: MemoryStore | PostgresStore, tenant_id: str, mapping_id: str,
    query_sem: np.ndarray, top_k: int, category_filter: str | None,
) -> list[dict]:
    chunks = store.list_chunks(tenant_id, mapping_id, category_filter=category_filter)
    scored: list[tuple[ChunkRecord, float]] = []
    for rec in chunks:
        vec = rec.sem_embedding.copy()
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        scored.append((rec, float(vec @ query_sem)))
    scored.sort(key=lambda x: x[1], reverse=True)
    hits = []
    for rec, sim in scored[:top_k]:
        hit = _to_hit(rec, [])
        hit["score"] = sim
        hits.append(hit)
    return hits


def _empty(tenant_id: str, query: str, mapping_id: str) -> dict:
    return {
        "query": query,
        "tenant_id": tenant_id,
        "mapping_id": mapping_id,
        "retrieval_mode": "empty",
        "hits": [],
        "results": [],
        "communities": [],
    }
