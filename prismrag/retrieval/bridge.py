"""PrismRAG AP001.2 — Bridge vector injection between two communities."""
from __future__ import annotations

import json
import logging

import numpy as np

from prismrag.db import get_conn, release_conn, vector_to_pg
from prismrag.graph.community import _label_community

logger = logging.getLogger(__name__)


def create_bridge_vector(
    tenant_id: str,
    mapping_id: str,
    community_a: int,
    community_b: int,
    label_override: str | None = None,
) -> dict:
    """
    Compute and persist a bridge vector between two communities.

    Bridge vector = normalised midpoint of the two community centroids,
    stored in both 256-d personal space and 768-d semantic space.

    The bridge node appears in retrieval as a connector — queries that
    match community A or B will traverse to the other via this node.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT community_id, centroid_vec::text, top_words
            FROM prismrag.community_summary
            WHERE tenant_id = %s AND mapping_id = %s
              AND community_id IN (%s, %s)
            """,
            (tenant_id, mapping_id, community_a, community_b),
        )
        rows = {r[0]: r for r in cur.fetchall()}
    finally:
        release_conn(conn)

    if community_a not in rows or community_b not in rows:
        raise ValueError(
            f"Both communities {community_a} and {community_b} must exist "
            f"for tenant {tenant_id} / mapping {mapping_id}"
        )

    row_a = rows[community_a]
    row_b = rows[community_b]

    # Compute bridge as normalised midpoint in semantic (768-d) space
    sem_a = np.array(json.loads(row_a[1]), dtype=float)
    sem_b = np.array(json.loads(row_b[1]), dtype=float)
    sem_bridge = (sem_a + sem_b) / 2.0
    norm = np.linalg.norm(sem_bridge)
    if norm > 0:
        sem_bridge /= norm

    # Project to 256-d personal space via MLP (or random projection fallback)
    personal_bridge = _project_bridge(tenant_id, mapping_id, sem_bridge)

    # Generate bridge label
    if label_override:
        label = label_override
    else:
        top_a = list(row_a[2] or [])[:5]
        top_b = list(row_b[2] or [])[:5]
        try:
            bridge_words = top_a + top_b
            label, _ = _label_community(bridge_words)
            label = f"Bridge: {label}"
        except Exception:
            label = f"Bridge: community {community_a} ↔ {community_b}"

    # Persist
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prismrag.bridge_vector
                (tenant_id, mapping_id, community_a, community_b, label, embedding, sem_embedding)
            VALUES (%s, %s, %s, %s, %s, %s::vector, %s::vector)
            ON CONFLICT (tenant_id, mapping_id, community_a, community_b) DO UPDATE
            SET label         = EXCLUDED.label,
                embedding     = EXCLUDED.embedding,
                sem_embedding = EXCLUDED.sem_embedding
            RETURNING id
            """,
            (
                tenant_id, mapping_id, community_a, community_b, label,
                vector_to_pg(personal_bridge.tolist()),
                vector_to_pg(sem_bridge.tolist()),
            ),
        )
        bridge_id = int(cur.fetchone()[0])

        # Also add a graph edge connecting the two communities via the bridge
        _add_bridge_edges(cur, tenant_id, mapping_id, community_a, community_b, label)
        conn.commit()
    finally:
        release_conn(conn)

    logger.info(
        "Bridge %d created: community %d ↔ %d (%s) for tenant %s",
        bridge_id, community_a, community_b, label, tenant_id[:8]
    )

    return {
        "bridge_id":   bridge_id,
        "tenant_id":   tenant_id,
        "mapping_id":  mapping_id,
        "community_a": community_a,
        "community_b": community_b,
        "label":       label,
    }


def _project_bridge(tenant_id: str, mapping_id: str, sem_bridge: np.ndarray) -> np.ndarray:
    """Project 768-d bridge vector to 256-d personal space using MLP or random projection."""
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

        if row:
            from prismrag.mapping.mlp import load_mlp
            import torch
            model = load_mlp(bytes(row[0]))
            with torch.no_grad():
                t = torch.tensor(sem_bridge[np.newaxis, :], dtype=torch.float32)
                return model(t).numpy()[0]
    except Exception:
        pass

    # Fallback: same deterministic random projection as RulesStrategy
    rng = np.random.RandomState(seed=42)
    mat = rng.randn(256, 768).astype(float)
    q, _ = np.linalg.qr(mat.T)
    proj = q.T[:256]
    out  = proj @ sem_bridge
    norm = np.linalg.norm(out)
    return (out / norm) if norm > 0 else out


def _add_bridge_edges(cur, tenant_id, mapping_id, community_a, community_b, label):
    """Add word_graph_edge rows connecting top words of the two communities."""
    cur.execute(
        "SELECT top_words FROM prismrag.community_summary "
        "WHERE tenant_id = %s AND mapping_id = %s AND community_id = ANY(%s)",
        (tenant_id, mapping_id, [community_a, community_b]),
    )
    rows   = cur.fetchall()
    words_a = list(rows[0][0] or [])[:3] if len(rows) > 0 else []
    words_b = list(rows[1][0] or [])[:3] if len(rows) > 1 else []

    for wa in words_a:
        for wb in words_b:
            cur.execute(
                """
                INSERT INTO prismrag.word_graph_edge
                    (tenant_id, mapping_id, from_word, to_word, edge_type, weight)
                VALUES (%s, %s, %s, %s, 'bridge', 0.5)
                ON CONFLICT DO NOTHING
                """,
                (tenant_id, mapping_id, wa, wb),
            )
