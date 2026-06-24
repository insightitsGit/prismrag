"""Bridge vectors between communities (parity with SaaS prismrag.retrieval.bridge)."""
from __future__ import annotations

from typing import Callable

import numpy as np

from prismrag_patch.mapping.projection import project_sem_to_personal, projection_matrix
from prismrag_patch.store.memory import MemoryStore
from prismrag_patch.store.postgres import PostgresStore


def create_bridge(
    store: MemoryStore | PostgresStore,
    tenant_id: str,
    mapping_id: str,
    community_a: int,
    community_b: int,
    label_override: str | None = None,
    label_fn: Callable[[list[str]], tuple[str, str]] | None = None,
) -> dict:
    row_a = store.get_community(tenant_id, mapping_id, community_a)
    row_b = store.get_community(tenant_id, mapping_id, community_b)
    if row_a is None or row_b is None:
        raise ValueError(
            f"Both communities {community_a} and {community_b} must exist "
            f"for tenant {tenant_id} / mapping {mapping_id}"
        )

    sem_a = np.array(row_a.centroid_vec, dtype=float)
    sem_b = np.array(row_b.centroid_vec, dtype=float)
    sem_bridge = (sem_a + sem_b) / 2.0
    norm = np.linalg.norm(sem_bridge)
    if norm > 0:
        sem_bridge /= norm

    cfg = store.get_mapping_config(mapping_id)
    categories = [c["slug"] for c in cfg.categories] if cfg else ["default"]
    personal_bridge = _project_bridge(store, tenant_id, mapping_id, sem_bridge, categories)

    if label_override:
        label = label_override
    elif label_fn:
        top_a = list(row_a.top_words or [])[:5]
        top_b = list(row_b.top_words or [])[:5]
        lbl, _ = label_fn(top_a + top_b)
        label = f"Bridge: {lbl}"
    else:
        label = f"Bridge: community {community_a} ↔ {community_b}"

    rec = store.upsert_bridge(
        tenant_id, mapping_id, community_a, community_b,
        label, personal_bridge, sem_bridge,
    )

    _add_bridge_edges(store, tenant_id, mapping_id, row_a, row_b)

    return {
        "bridge_id": rec.bridge_id,
        "tenant_id": tenant_id,
        "mapping_id": mapping_id,
        "community_a": community_a,
        "community_b": community_b,
        "label": label,
    }


def _project_bridge(
    store: MemoryStore | PostgresStore, tenant_id: str, mapping_id: str,
    sem_bridge: np.ndarray, categories: list[str],
) -> np.ndarray:
    blob = store.load_mlp(tenant_id, mapping_id)
    if blob:
        try:
            from prismrag_patch.mapping.mlp import load_mlp
            import torch
            model = load_mlp(blob)
            with torch.no_grad():
                t = torch.tensor(sem_bridge[np.newaxis, :], dtype=torch.float32)
                return model(t).numpy()[0]
        except Exception:
            pass

    slug = categories[0] if categories else "default"
    return project_sem_to_personal(sem_bridge, slug, categories)


def _add_bridge_edges(store, tenant_id, mapping_id, row_a, row_b) -> None:
    words_a = list(row_a.top_words or [])[:3]
    words_b = list(row_b.top_words or [])[:3]
    for wa in words_a:
        for wb in words_b:
            store.add_edge(tenant_id, mapping_id, wa, wb, "bridge", 0.5)
