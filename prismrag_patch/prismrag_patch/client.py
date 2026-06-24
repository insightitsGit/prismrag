"""PrismRAG — high-level client (API parity for pip-only OSS use)."""
from __future__ import annotations

import uuid
from typing import Any, Callable

from prismrag_patch.embedding.deterministic import embed_texts, make_embed_fn
from prismrag_patch.graph.community import default_label_fn
from prismrag_patch.models import (
    AppendChunkResult,
    AppendRequest,
    ChunkIn,
    InlineRecord,
    MappingConfig,
    RuleIn,
)
from prismrag_patch.pipeline.append import run_append
from prismrag_patch.pipeline.ingest import run_ingest
from prismrag_patch.pipeline.quality import score_batch, summarise_quality
from prismrag_patch.retrieval.bridge import create_bridge
from prismrag_patch.retrieval.search import retrieve
from prismrag_patch.store import MemoryStore, PostgresStore


class PrismRAG:
    """
    Unified OSS client mirroring SaaS core RAG endpoints.

    Example::

        from prismrag_patch import PrismRAG
        from tests.conftest import HEALTHCARE_MAPPING

        rag = PrismRAG(mapping=HEALTHCARE_MAPPING, tenant_id="demo")
        job = rag.ingest(records=[{"word": "diabetes", "text": "diabetes management"}])
        results = rag.search("What medications for diabetes?", top_k=5)
        communities = rag.list_communities()
    """

    def __init__(
        self,
        mapping: dict[str, Any] | MappingConfig,
        tenant_id: str | None = None,
        embed_fn: Callable[[list[str]], list[list[float] | None]] | None = None,
        store: MemoryStore | PostgresStore | None = None,
        label_fn: Callable | None = None,
        auto_ensure_tenant: bool = True,
    ) -> None:
        self.tenant_id = tenant_id or str(uuid.uuid4())
        self.mapping = mapping if isinstance(mapping, MappingConfig) else MappingConfig.from_dict(mapping)
        self.embed_fn = embed_fn or embed_texts
        self.store = store or MemoryStore()
        self.label_fn = label_fn or default_label_fn
        self._model = None
        if auto_ensure_tenant and isinstance(self.store, PostgresStore):
            self.store.ensure_tenant(self.tenant_id)

    @classmethod
    def from_postgres(
        cls,
        dsn: str,
        mapping: dict[str, Any] | MappingConfig,
        tenant_id: str,
        embed_fn: Callable | None = None,
        **kwargs: Any,
    ) -> "PrismRAG":
        """Construct a client backed by the SaaS ``prismrag.*`` Postgres schema."""
        store = PostgresStore(dsn=dsn)
        return cls(
            mapping=mapping,
            tenant_id=tenant_id,
            embed_fn=embed_fn,
            store=store,
            **kwargs,
        )

    # ── Ingest / jobs ─────────────────────────────────────────────────────────

    def ingest(
        self,
        records: list[dict[str, Any] | InlineRecord] | None = None,
        *,
        inline_config: dict[str, Any] | None = None,
        strategy: str = "rules",
        wait: bool = True,
    ) -> dict[str, Any]:
        """Submit and run an inline ingest job (sync by default)."""
        recs = self._normalize_records(records, inline_config)
        job_id = self.store.create_job(self.tenant_id, "inline")
        if not wait:
            return {"job_id": job_id, "status": "queued"}
        return run_ingest(
            self.store,
            self.tenant_id,
            job_id,
            self.mapping,
            recs,
            embed_fn=self.embed_fn,
            strategy=strategy,
            label_fn=self.label_fn,
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found")
        return self.store.job_to_dict(job)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_filter: str | None = None,
        mapping_id: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        out = retrieve(
            self.store,
            self.tenant_id,
            query,
            self.embed_fn,
            mapping_id=mapping_id,
            top_k=top_k,
            category_filter=category_filter,
            model=self._model,
        )
        if mode and out["retrieval_mode"] != mode and mode != "auto":
            pass
        return out

    # ── Communities / bridges ─────────────────────────────────────────────────

    def list_communities(self, mapping_id: str | None = None) -> list[dict[str, Any]]:
        mid = mapping_id or self.store.latest_mapping(self.tenant_id)
        if not mid:
            return []
        return [
            {
                "id": c.community_id,
                "community_id": c.community_id,
                "label": c.label,
                "summary_text": c.summary_text,
                "top_words": c.top_words,
                "word_count": c.word_count,
            }
            for c in self.store.list_communities(self.tenant_id, mid)
        ]

    def create_bridge(
        self,
        community_a: int,
        community_b: int,
        bridge_label: str | None = None,
        mapping_id: str | None = None,
    ) -> dict[str, Any]:
        mid = mapping_id or self.store.latest_mapping(self.tenant_id)
        if not mid:
            raise ValueError("No active mapping — ingest first")
        return create_bridge(
            self.store,
            self.tenant_id,
            mid,
            community_a,
            community_b,
            label_override=bridge_label,
            label_fn=self.label_fn,
        )

    # ── Append / quality ──────────────────────────────────────────────────────

    def append_chunks(
        self,
        chunks: list[dict[str, Any] | ChunkIn],
        new_rules: list[dict[str, Any] | RuleIn] | None = None,
        ml_fallback: str = "auto",
        include_vectors: bool = False,
    ) -> list[dict[str, Any]]:
        req = AppendRequest(
            chunks=[
                ChunkIn(ref=c["ref"] if isinstance(c, dict) else c.ref,
                        text=c["text"] if isinstance(c, dict) else c.text)
                for c in chunks
            ],
            new_rules=[
                RuleIn(
                    word=r["word"] if isinstance(r, dict) else r.word,
                    category_slug=r["category_slug"] if isinstance(r, dict) else r.category_slug,
                    weight=float(r.get("weight", 1.0) if isinstance(r, dict) else r.weight),
                )
                for r in (new_rules or [])
            ],
            ml_fallback=ml_fallback,
            include_vectors=include_vectors,
        )
        results = run_append(self.store, self.tenant_id, req, embed_fn=self.embed_fn)
        return [r.to_dict() for r in results]

    def chunk_quality(self, mapping_id: str | None = None) -> dict[str, Any]:
        mid = mapping_id or self.store.latest_mapping(self.tenant_id)
        if not mid:
            return summarise_quality([])
        chunks = self.store.all_chunks(self.tenant_id, mid)
        import numpy as np
        refs = [c.chunk_ref for c in chunks]
        embs = np.array([c.embedding for c in chunks], dtype=float)
        cats = [c.category_slug for c in chunks]
        scores = [q._asdict() for q in score_batch(refs, embs, cats)]
        return {"scores": scores, "summary": summarise_quality(scores)}

    def export_chunks(self, mapping_id: str | None = None) -> list[dict[str, Any]]:
        mid = mapping_id or self.store.latest_mapping(self.tenant_id)
        if not mid:
            return []
        return [
            {
                "chunk_ref": c.chunk_ref,
                "chunk_text": c.chunk_text,
                "category_slug": c.category_slug,
                "community_id": c.community_id,
                "embedding": c.embedding.tolist(),
                "sem_embedding": c.sem_embedding.tolist(),
                "metadata": c.metadata,
            }
            for c in self.store.all_chunks(self.tenant_id, mid)
        ]

    @staticmethod
    def _normalize_records(
        records: list[dict[str, Any] | InlineRecord] | None,
        inline_config: dict[str, Any] | None,
    ) -> list[InlineRecord]:
        raw = records
        if raw is None and inline_config:
            raw = inline_config.get("records", [])
        if not raw:
            raise ValueError("records or inline_config.records required")
        out: list[InlineRecord] = []
        for r in raw:
            if isinstance(r, InlineRecord):
                out.append(r)
            else:
                out.append(InlineRecord(
                    word=r["word"],
                    text=r.get("text"),
                    category_hint=r.get("category_hint"),
                ))
        return out
