"""Append mode — extend mapping with new chunks (rules strategy parity)."""
from __future__ import annotations

import numpy as np

from prismrag_patch.mapping.rules import RulesStrategy
from prismrag_patch.models import AppendChunkResult, AppendRequest, MappingConfig
from prismrag_patch.pipeline.quality import score_batch
from prismrag_patch.store.memory import MemoryStore
from prismrag_patch.store.postgres import PostgresStore


def run_append(
    store: MemoryStore | PostgresStore,
    tenant_id: str,
    request: AppendRequest,
    embed_fn=None,
) -> list[AppendChunkResult]:
    mapping_id = store.latest_mapping(tenant_id)
    if not mapping_id:
        raise ValueError(
            f"No active mapping for tenant {tenant_id}. "
            "Run ingest first to create the initial mapping."
        )

    cfg = store.get_mapping_config(mapping_id)
    if cfg is None:
        raise ValueError(f"Mapping {mapping_id} not found")

    if request.new_rules:
        cfg = store.merge_rules(mapping_id, [
            {"word": r.word, "category_slug": r.category_slug, "weight": r.weight}
            for r in request.new_rules
        ])

    strategy = RulesStrategy(cfg, embed_fn=embed_fn)
    refs = [c.ref for c in request.chunks]
    texts = [c.text for c in request.chunks]
    batch = [(c.ref, c.text, None) for c in request.chunks]
    mapped = strategy.assign_batch(batch)

    embs = np.array([m.embedding for m in mapped], dtype=float)
    cats = [m.category_slug for m in mapped]
    qualities = score_batch(refs, embs, cats)

    results: list[AppendChunkResult] = []
    for chunk, mapped_res, q in zip(request.chunks, mapped, qualities):
        cat = mapped_res.category_slug
        conf = q.confidence

        if request.ml_fallback in ("auto", "always"):
            rule_cat = strategy.infer_category_from_text(chunk.text)
            if rule_cat and request.ml_fallback == "always":
                cat = rule_cat
            elif rule_cat and q.flagged:
                rule_conf = 0.6
                if rule_conf > conf:
                    cat = rule_cat
                    conf = rule_conf

        store.upsert_chunk(
            tenant_id=tenant_id,
            mapping_id=mapping_id,
            chunk_ref=chunk.ref,
            chunk_text=chunk.text,
            category_slug=cat,
            embedding=mapped_res.embedding,
            sem_embedding=mapped_res.sem_embedding,
        )

        emb_out = mapped_res.embedding.tolist() if request.include_vectors else None
        results.append(AppendChunkResult(
            chunk_ref=chunk.ref,
            chunk_text=chunk.text,
            category_slug=cat,
            confidence=conf,
            separation=q.separation,
            coherence=q.coherence,
            quality_score=q.quality_score,
            flagged=q.flagged,
            embedding=emb_out,
        ))

    return results
