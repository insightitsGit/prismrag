"""PrismRAG — Louvain community detection + LLM labelling."""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests

from prismrag.config import GEMINI_API_KEY, GEMINI_LLM_MODEL, COMMUNITY_LABEL_WORKERS
from prismrag.db import get_conn, release_conn, vector_to_pg

logger = logging.getLogger(__name__)


def build_communities(tenant_id: str, mapping_id: str) -> int:
    """Run Louvain, label communities in parallel, persist. Returns community count."""
    try:
        import networkx as nx
        from community import best_partition   # python-louvain
    except ImportError:
        raise RuntimeError(
            "networkx and python-louvain are required: pip install networkx python-louvain"
        )

    # Load edges
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT from_word, to_word, weight FROM prismrag.word_graph_edge "
            "WHERE tenant_id = %s AND mapping_id = %s",
            (tenant_id, mapping_id),
        )
        edge_rows = cur.fetchall()

        cur.execute(
            "SELECT chunk_ref, category_slug, sem_embedding::text "
            "FROM prismrag.chunk_embedding "
            "WHERE tenant_id = %s AND mapping_id = %s AND sem_embedding IS NOT NULL",
            (tenant_id, mapping_id),
        )
        node_rows = cur.fetchall()
    finally:
        release_conn(conn)

    if not edge_rows:
        logger.info("No edges for community detection — skipping")
        return 0

    G = nx.Graph()
    for fw, tw, w in edge_rows:
        G.add_edge(fw, tw, weight=float(w))

    partition: dict[str, int] = best_partition(G)   # word → community_id

    # Build centroid per community
    word_sem: dict[str, np.ndarray] = {}
    for ref, _cat, sem_str in node_rows:
        if sem_str:
            word_sem[ref] = np.array(json.loads(sem_str), dtype=float)

    communities: dict[int, list[str]] = {}
    for word, cid in partition.items():
        communities.setdefault(cid, []).append(word)

    # Pre-compute centroid and top_words
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

    # Label communities in parallel
    labels: dict[int, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=COMMUNITY_LABEL_WORKERS) as pool:
        futures = {
            pool.submit(_label_community, m["top_words"]): m["community_id"]
            for m in comm_meta if m["top_words"]
        }
        for future in as_completed(futures):
            cid = futures[future]
            try:
                labels[cid] = future.result()
            except Exception as exc:
                logger.warning("Label failed for community %d: %s", cid, exc)

    # Persist
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM prismrag.community_member WHERE tenant_id = %s AND mapping_id = %s",
            (tenant_id, mapping_id),
        )
        cur.execute(
            "DELETE FROM prismrag.community_summary WHERE tenant_id = %s AND mapping_id = %s",
            (tenant_id, mapping_id),
        )

        for meta in comm_meta:
            cid      = meta["community_id"]
            members  = meta["members"]
            centroid = meta["centroid"]
            top_words = meta["top_words"]
            centroid_pg = vector_to_pg(centroid.tolist()) if centroid is not None else None

            for word in members:
                cur.execute(
                    """
                    INSERT INTO prismrag.community_member
                        (tenant_id, mapping_id, word, community_id, centroid_vec)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    ON CONFLICT (tenant_id, mapping_id, word) DO UPDATE
                    SET community_id = EXCLUDED.community_id,
                        centroid_vec = EXCLUDED.centroid_vec
                    """,
                    (tenant_id, mapping_id, word, cid, centroid_pg),
                )

            label, summary = labels.get(cid, (",".join(top_words[:3]), ""))
            cur.execute(
                """
                INSERT INTO prismrag.community_summary
                    (tenant_id, mapping_id, community_id, label, summary_text,
                     top_words, word_count, centroid_vec)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (tenant_id, mapping_id, community_id) DO UPDATE
                SET label        = EXCLUDED.label,
                    summary_text = EXCLUDED.summary_text,
                    top_words    = EXCLUDED.top_words,
                    word_count   = EXCLUDED.word_count,
                    centroid_vec = EXCLUDED.centroid_vec
                """,
                (tenant_id, mapping_id, cid, label, summary,
                 top_words, len(members), centroid_pg),
            )

        conn.commit()
        logger.info("Persisted %d communities for tenant %s", len(comm_meta), tenant_id[:8])
    finally:
        release_conn(conn)

    return len(comm_meta)


def _label_community(top_words: list[str]) -> tuple[str, str]:
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or ""
    if not api_key or not top_words:
        return ", ".join(top_words[:3]), f"Related: {', '.join(top_words[:6])}"

    word_list = ", ".join(top_words[:12])
    prompt = (
        f"These words form a semantic cluster: {word_list}.\n"
        f"Provide (1) a 1-3 word label and (2) a single sentence describing the theme.\n"
        f'Reply ONLY as JSON: {{"label": "...", "summary": "..."}}'
    )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_LLM_MODEL}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 128},
    }
    try:
        import re
        resp = requests.post(url, json=body, timeout=20)
        resp.raise_for_status()
        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        raw = "\n".join(p.get("text", "") for p in parts).strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE).strip("`").strip()
        parsed = json.loads(raw)
        return parsed.get("label", top_words[0]), parsed.get("summary", "")
    except Exception as exc:
        logger.warning("Community label API error: %s", exc)
        return ", ".join(top_words[:3]), f"Related: {', '.join(top_words[:6])}"
