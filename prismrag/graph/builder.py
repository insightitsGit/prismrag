"""PrismRAG — Word graph builder.

Builds two edge types:
  rule   — explicit word→word edges within the same category (weight=1.0)
  semantic — Gemini cosine ≥ SEM_EDGE_THRESHOLD (weight=cosine)
"""
from __future__ import annotations

import logging

import numpy as np

from prismrag.config import SEM_EDGE_THRESHOLD
from prismrag.db import get_conn, release_conn

logger = logging.getLogger(__name__)


def build_graph(tenant_id: str, mapping_id: str) -> int:
    """Build word graph edges for a tenant/mapping. Returns edge count."""
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Load all chunk embeddings (word + sem_embedding + category)
        cur.execute(
            """
            SELECT chunk_ref, category_slug,
                   embedding::text, sem_embedding::text
            FROM prismrag.chunk_embedding
            WHERE tenant_id = %s AND mapping_id = %s
              AND sem_embedding IS NOT NULL
            """,
            (tenant_id, mapping_id),
        )
        rows = cur.fetchall()
    finally:
        release_conn(conn)

    if not rows:
        return 0

    import json
    words      = [r[0] for r in rows]
    categories = [r[1] for r in rows]
    sem_vecs   = np.array([json.loads(r[3]) for r in rows], dtype=float)

    # Normalise for cosine
    norms = np.linalg.norm(sem_vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    sem_norm = sem_vecs / norms

    edges: list[tuple] = []

    # Rule edges: all pairs within the same category
    from collections import defaultdict
    by_cat: dict[str, list[int]] = defaultdict(list)
    for i, cat in enumerate(categories):
        if cat:
            by_cat[cat].append(i)

    for cat_idxs in by_cat.values():
        for i in range(len(cat_idxs)):
            for j in range(i + 1, len(cat_idxs)):
                a, b = cat_idxs[i], cat_idxs[j]
                edges.append((words[a], words[b], "rule", 1.0))

    # Semantic edges: cosine ≥ threshold (cap per word to avoid huge fan-out)
    sim_matrix = sem_norm @ sem_norm.T   # (N, N)
    np.fill_diagonal(sim_matrix, 0.0)

    for i in range(len(words)):
        row = sim_matrix[i]
        neighbors = np.where(row >= SEM_EDGE_THRESHOLD)[0]
        # Limit to top-20 semantic neighbours per word
        if len(neighbors) > 20:
            neighbors = neighbors[np.argsort(-row[neighbors])[:20]]
        for j in neighbors:
            if j <= i:
                continue
            edges.append((words[i], words[j], "semantic", float(row[j])))

    # Persist edges
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM prismrag.word_graph_edge WHERE tenant_id = %s AND mapping_id = %s",
            (tenant_id, mapping_id),
        )
        for fw, tw, etype, w in edges:
            cur.execute(
                """
                INSERT INTO prismrag.word_graph_edge
                    (tenant_id, mapping_id, from_word, to_word, edge_type, weight)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (tenant_id, mapping_id, fw, tw, etype, w),
            )
        conn.commit()
        logger.info("Built %d graph edges for tenant %s / mapping %s",
                    len(edges), tenant_id[:8], mapping_id[:8])
    finally:
        release_conn(conn)

    return len(edges)
