"""Word graph builder (parity with SaaS prismrag.graph.builder)."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from prismrag_patch.config import SEM_EDGE_THRESHOLD
from prismrag_patch.store.memory import MemoryStore
from prismrag_patch.store.postgres import PostgresStore
from prismrag_patch.store.types import GraphEdge


def build_graph(store: MemoryStore | PostgresStore, tenant_id: str, mapping_id: str) -> int:
    rows = store.all_chunks(tenant_id, mapping_id)
    if not rows:
        store.set_edges(tenant_id, mapping_id, [])
        return 0

    words = [r.chunk_ref for r in rows]
    categories = [r.category_slug for r in rows]
    sem_vecs = np.array([r.sem_embedding for r in rows], dtype=float)

    norms = np.linalg.norm(sem_vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    sem_norm = sem_vecs / norms

    edges: list[GraphEdge] = []

    by_cat: dict[str, list[int]] = defaultdict(list)
    for i, cat in enumerate(categories):
        if cat:
            by_cat[cat].append(i)

    for cat_idxs in by_cat.values():
        for i in range(len(cat_idxs)):
            for j in range(i + 1, len(cat_idxs)):
                a, b = cat_idxs[i], cat_idxs[j]
                edges.append(GraphEdge(words[a], words[b], "rule", 1.0))

    sim_matrix = sem_norm @ sem_norm.T
    np.fill_diagonal(sim_matrix, 0.0)

    for i in range(len(words)):
        row = sim_matrix[i]
        neighbors = np.where(row >= SEM_EDGE_THRESHOLD)[0]
        if len(neighbors) > 20:
            neighbors = neighbors[np.argsort(-row[neighbors])[:20]]
        for j in neighbors:
            if j <= i:
                continue
            edges.append(GraphEdge(words[i], words[j], "semantic", float(row[j])))

    store.set_edges(tenant_id, mapping_id, edges)
    return len(edges)
