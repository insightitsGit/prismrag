"""Louvain community detection (parity with SaaS prismrag.graph.community)."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import numpy as np

from prismrag_patch.store.memory import MemoryStore
from prismrag_patch.store.postgres import PostgresStore
from prismrag_patch.store.types import CommunitySummary

logger = logging.getLogger(__name__)


def build_communities(
    store: MemoryStore | PostgresStore,
    tenant_id: str,
    mapping_id: str,
    label_fn: Callable[[list[str]], tuple[str, str]] | None = None,
) -> int:
    try:
        import networkx as nx
        from community import best_partition
    except ImportError as exc:
        raise RuntimeError(
            "networkx and python-louvain are required: pip install networkx python-louvain"
        ) from exc

    edges = store.get_edges(tenant_id, mapping_id)
    if not edges:
        return 0

    G = nx.Graph()
    for e in edges:
        G.add_edge(e.from_word, e.to_word, weight=float(e.weight))

    partition: dict[str, int] = best_partition(G)

    chunks = store.all_chunks(tenant_id, mapping_id)
    word_sem: dict[str, np.ndarray] = {c.chunk_ref: c.sem_embedding for c in chunks}

    communities: dict[int, list[str]] = {}
    for word, cid in partition.items():
        communities.setdefault(cid, []).append(word)

    comm_meta: list[dict] = []
    for cid, members in communities.items():
        vecs = [word_sem[w] for w in members if w in word_sem]
        centroid = np.mean(vecs, axis=0) if vecs else None
        top_words = sorted(members, key=lambda w: G.degree(w), reverse=True)[:10]
        comm_meta.append({
            "community_id": cid,
            "members": members,
            "centroid": centroid,
            "top_words": top_words,
        })

    labels: dict[int, tuple[str, str]] = {}
    if label_fn:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(label_fn, m["top_words"]): m["community_id"]
                for m in comm_meta if m["top_words"]
            }
            for future in as_completed(futures):
                cid = futures[future]
                try:
                    labels[cid] = future.result()
                except Exception as exc:
                    logger.warning("Label failed for community %d: %s", cid, exc)

    summaries: list[CommunitySummary] = []
    members_map: dict[str, int] = {}
    for meta in comm_meta:
        cid = meta["community_id"]
        members = meta["members"]
        centroid = meta["centroid"]
        top_words = meta["top_words"]
        label, summary = labels.get(cid, (",".join(top_words[:3]), ""))
        summaries.append(CommunitySummary(
            community_id=cid,
            label=label,
            summary_text=summary,
            top_words=top_words,
            word_count=len(members),
            centroid_vec=centroid,
        ))
        for word in members:
            members_map[word] = cid

    store.set_communities(tenant_id, mapping_id, summaries, members_map)
    return len(summaries)


def default_label_fn(top_words: list[str]) -> tuple[str, str]:
    if not top_words:
        return "unknown", ""
    return ", ".join(top_words[:3]), f"Related: {', '.join(top_words[:6])}"
