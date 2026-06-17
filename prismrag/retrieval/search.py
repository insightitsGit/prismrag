"""PrismRAG — Retrieval: Graph RAG primary, HNSW direct fallback."""
from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np

from prismrag.config import (
    RETRIEVAL_TOP_K, RETRIEVAL_TOP_COMMUNITIES, BFS_MAX_HOPS, BFS_MAX_WORDS
)
from prismrag.db import get_conn, release_conn, vector_to_pg
from prismrag.embedding.gemini import embed_texts

logger = logging.getLogger(__name__)


def retrieve(
    tenant_id: str,
    query: str,
    mapping_id: str | None = None,
    top_k: int = RETRIEVAL_TOP_K,
    category_filter: str | None = None,
) -> dict[str, Any]:
    """Full retrieval pipeline. Returns dict matching SearchResponse schema."""

    # Resolve latest active mapping if not specified
    if not mapping_id:
        mapping_id = _latest_mapping(tenant_id)
    if not mapping_id:
        return _empty(tenant_id, query, mapping_id or "")

    # Load MLP model if Tier-2 artifact exists (for re-ranking)
    model = _load_mlp(tenant_id, mapping_id)

    # 1. Embed query with Gemini (768-d)
    query_tokens = [t for t in query.lower().split() if len(t) > 1]
    vecs = embed_texts(query_tokens or [query])
    valid = [np.array(v, dtype=float) for v in vecs if v is not None]
    if not valid:
        return _empty(tenant_id, query, mapping_id)

    query_sem = np.mean(valid, axis=0)
    norm = np.linalg.norm(query_sem)
    if norm > 0:
        query_sem /= norm

    # 2. Try Graph RAG path
    communities = _get_communities(tenant_id, mapping_id)
    hits, community_context, mode = [], [], "direct"

    if communities:
        try:
            hits, community_context = _graph_retrieve(
                tenant_id, mapping_id, query_sem, query_tokens,
                communities, model, top_k, category_filter
            )
            mode = "graph_rag"
        except Exception as exc:
            logger.warning("Graph RAG failed, falling back to direct: %s", exc)

    # 3. Fallback: direct HNSW cosine on sem_embedding
    if not hits:
        hits = _direct_retrieve(tenant_id, mapping_id, query_sem, top_k, category_filter)
        mode = "direct"

    return {
        "query":          query,
        "tenant_id":      tenant_id,
        "mapping_id":     mapping_id,
        "retrieval_mode": mode,
        "hits":           hits,
        "communities":    community_context,
    }


# ── Graph RAG path ────────────────────────────────────────────────────────────

def _graph_retrieve(
    tenant_id, mapping_id, query_sem, query_tokens,
    communities, model, top_k, category_filter
):
    # 2a. Find top communities by centroid cosine
    ranked_comms = _rank_communities(tenant_id, mapping_id, query_sem, communities)

    # 2b. Seed words from top communities
    seed_words: list[str] = []
    for cid, _ in ranked_comms[:RETRIEVAL_TOP_COMMUNITIES]:
        comm = next((c for c in communities if c["community_id"] == cid), None)
        if comm:
            seed_words.extend(comm.get("top_words") or [])
    seed_words.extend(query_tokens)
    seed_words = list(dict.fromkeys(seed_words))

    # 2c. BFS expand
    expanded = _bfs_expand(tenant_id, mapping_id, seed_words)

    # 2d. Fetch chunk texts for candidates
    candidates = list(dict.fromkeys(seed_words + expanded))
    chunks = _fetch_chunks(tenant_id, mapping_id, candidates, category_filter)
    if not chunks:
        return [], []

    # 2e. MLP re-rank (if model available) else semantic re-rank
    if model:
        chunks = _mlp_rerank(model, query_tokens, chunks, top_k)
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


def _rank_communities(tenant_id, mapping_id, query_sem, communities):
    conn = get_conn()
    try:
        cur = conn.cursor()
        query_pg = vector_to_pg(query_sem.tolist())
        cur.execute(
            """
            SELECT community_id,
                   1 - (centroid_vec <=> %s::vector) AS similarity
            FROM prismrag.community_summary
            WHERE tenant_id = %s AND mapping_id = %s AND centroid_vec IS NOT NULL
            ORDER BY centroid_vec <=> %s::vector
            LIMIT %s
            """,
            (query_pg, tenant_id, mapping_id, query_pg, RETRIEVAL_TOP_COMMUNITIES * 3),
        )
        rows = cur.fetchall()
    finally:
        release_conn(conn)

    if not rows:
        return []

    scored = sorted(rows, key=lambda r: r[1], reverse=True)[:RETRIEVAL_TOP_COMMUNITIES]
    vals   = np.array([float(s) for _, s in scored])
    vals   = vals - vals.max()
    weights = np.exp(vals)
    weights /= weights.sum()
    return [(int(cid), float(w)) for (cid, _), w in zip(scored, weights)]


def _bfs_expand(tenant_id, mapping_id, seed_words):
    if not seed_words:
        return []
    conn = get_conn()
    try:
        cur = conn.cursor()
        visited = set(seed_words)
        frontier = list(seed_words)

        for _ in range(BFS_MAX_HOPS):
            if not frontier or len(visited) >= BFS_MAX_WORDS:
                break
            ph = ",".join(["%s"] * len(frontier))
            cur.execute(
                f"""
                SELECT DISTINCT to_word FROM prismrag.word_graph_edge
                WHERE tenant_id = %s AND mapping_id = %s AND from_word IN ({ph})
                UNION
                SELECT DISTINCT from_word FROM prismrag.word_graph_edge
                WHERE tenant_id = %s AND mapping_id = %s AND to_word IN ({ph})
                """,
                (tenant_id, mapping_id, *frontier, tenant_id, mapping_id, *frontier),
            )
            new = [r[0] for r in cur.fetchall() if r[0] not in visited]
            visited.update(new[:BFS_MAX_WORDS - len(visited)])
            frontier = new[:BFS_MAX_WORDS - len(visited)]

        return list(visited)
    finally:
        release_conn(conn)


def _fetch_chunks(tenant_id, mapping_id, candidates, category_filter):
    if not candidates:
        return []
    conn = get_conn()
    try:
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(candidates))
        cat_clause = "AND category_slug = %s" if category_filter else ""
        args = [tenant_id, mapping_id, *candidates]
        if category_filter:
            args.append(category_filter)
        cur.execute(
            f"""
            SELECT chunk_text, chunk_ref, category_slug, community_id,
                   embedding::text, sem_embedding::text, metadata_json
            FROM prismrag.chunk_embedding
            WHERE tenant_id = %s AND mapping_id = %s
              AND chunk_ref IN ({ph}) {cat_clause}
            """,
            args,
        )
        return cur.fetchall()
    finally:
        release_conn(conn)


def _mlp_rerank(model, query_tokens, chunks, top_k):
    try:
        import torch
        token_texts = query_tokens or ["query"]
        token_vecs_raw = embed_texts(token_texts)
        token_arr = np.array([v for v in token_vecs_raw if v is not None], dtype=float)
        if token_arr.shape[0] == 0:
            return chunks[:top_k]

        with torch.no_grad():
            t_in  = torch.tensor(token_arr, dtype=torch.float32)
            t_out = model(t_in).numpy()   # (T, 256)

        scored = []
        for row in chunks:
            emb_str = row[4]
            if not emb_str:
                scored.append((row, 0.0))
                continue
            vec = np.array(json.loads(emb_str), dtype=float)
            sim = float((vec @ t_out.T).max())
            scored.append((row, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]
    except Exception:
        return chunks[:top_k]


def _sem_rerank(query_sem, chunks, top_k):
    scored = []
    for row in chunks:
        sem_str = row[5]
        if not sem_str:
            scored.append((row, 0.0))
            continue
        vec  = np.array(json.loads(sem_str), dtype=float)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        sim = float(vec @ query_sem)
        scored.append((row, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scored[:top_k]]


def _to_hit(row, communities) -> dict:
    cid = row[3]
    comm_label = next((c["label"] for c in communities if c["community_id"] == cid), None)
    meta = row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}")
    return {
        "chunk_text":     row[0],
        "chunk_ref":      row[1],
        "category_slug":  row[2],
        "community_id":   cid,
        "community_label": comm_label,
        "score":          0.0,
        "metadata":       meta,
    }


# ── Direct HNSW fallback ──────────────────────────────────────────────────────

def _direct_retrieve(tenant_id, mapping_id, query_sem, top_k, category_filter):
    conn = get_conn()
    try:
        cur = conn.cursor()
        query_pg = vector_to_pg(query_sem.tolist())
        cat_clause = "AND category_slug = %s" if category_filter else ""
        args = [query_pg, tenant_id, mapping_id, query_pg, top_k]
        if category_filter:
            args.insert(3, category_filter)
        cur.execute(
            f"""
            SELECT chunk_text, chunk_ref, category_slug, community_id,
                   1 - (sem_embedding <=> %s::vector) AS score,
                   metadata_json
            FROM prismrag.chunk_embedding
            WHERE tenant_id = %s AND mapping_id = %s
              AND sem_embedding IS NOT NULL {cat_clause}
            ORDER BY sem_embedding <=> %s::vector
            LIMIT %s
            """,
            args,
        )
        rows = cur.fetchall()
    finally:
        release_conn(conn)

    return [
        {
            "chunk_text":    r[0],
            "chunk_ref":     r[1],
            "category_slug": r[2],
            "community_id":  r[3],
            "community_label": None,
            "score":         float(r[4]),
            "metadata":      r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}"),
        }
        for r in rows
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_communities(tenant_id, mapping_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT community_id, label, summary_text, top_words, word_count "
            "FROM prismrag.community_summary "
            "WHERE tenant_id = %s AND mapping_id = %s ORDER BY word_count DESC",
            (tenant_id, mapping_id),
        )
        return [
            {"community_id": r[0], "label": r[1], "summary_text": r[2],
             "top_words": r[3] or [], "word_count": r[4]}
            for r in cur.fetchall()
        ]
    finally:
        release_conn(conn)


def _latest_mapping(tenant_id) -> str | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM prismrag.mapping_version "
            "WHERE tenant_id = %s AND status = 'active' "
            "ORDER BY created_at DESC LIMIT 1",
            (tenant_id,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None
    finally:
        release_conn(conn)


def _load_mlp(tenant_id, mapping_id):
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT weights_blob FROM prismrag.mlp_artifact "
                "WHERE tenant_id = %s AND mapping_id = %s",
                (tenant_id, mapping_id),
            )
            row = cur.fetchone()
        finally:
            release_conn(conn)
        if not row:
            return None
        from prismrag.mapping.mlp import load_mlp
        return load_mlp(bytes(row[0]))
    except Exception:
        return None


def _empty(tenant_id, query, mapping_id):
    return {
        "query": query, "tenant_id": tenant_id, "mapping_id": mapping_id,
        "retrieval_mode": "empty", "hits": [], "communities": [],
    }
