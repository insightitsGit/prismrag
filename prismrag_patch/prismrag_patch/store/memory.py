"""In-memory store — full parity data model for local / test use."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from prismrag_patch.models import JobStatus, MappingConfig
from prismrag_patch.store.types import (
    BridgeRecord,
    ChunkRecord,
    CommunitySummary,
    GraphEdge,
    JobRecord,
)

__all__ = [
    "MemoryStore",
    "ChunkRecord",
    "GraphEdge",
    "CommunitySummary",
    "BridgeRecord",
    "JobRecord",
]


class MemoryStore:
    """Thread-unsafe in-memory backend mirroring SaaS DB tables."""

    def __init__(self) -> None:
        self._chunks: dict[tuple[str, str, str], ChunkRecord] = {}
        self._edges: dict[tuple[str, str], list[GraphEdge]] = {}
        self._communities: dict[tuple[str, str, int], CommunitySummary] = {}
        self._members: dict[tuple[str, str, str], int] = {}
        self._bridges: dict[tuple[str, str, int, int], BridgeRecord] = {}
        self._mappings: dict[str, dict[str, Any]] = {}
        self._active_mapping: dict[str, str] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._mlp_blobs: dict[tuple[str, str], bytes] = {}
        self._next_bridge_id = 1

    def ensure_tenant(self, tenant_id: str, name: str | None = None) -> None:
        """No-op for in-memory store."""

    def persist_mapping(
        self, tenant_id: str, mapping: MappingConfig, strategy: str = "rules"
    ) -> str:
        mapping_id = str(uuid.uuid4())
        for tid in list(self._active_mapping):
            if tid == tenant_id:
                old = self._active_mapping[tid]
                if old in self._mappings:
                    self._mappings[old]["status"] = "archived"
        self._mappings[mapping_id] = {
            "id": mapping_id,
            "tenant_id": tenant_id,
            "strategy": strategy,
            "status": "active",
            "config": mapping,
        }
        self._active_mapping[tenant_id] = mapping_id
        return mapping_id

    def latest_mapping(self, tenant_id: str) -> str | None:
        return self._active_mapping.get(tenant_id)

    def get_mapping_config(self, mapping_id: str) -> MappingConfig | None:
        m = self._mappings.get(mapping_id)
        if not m:
            return None
        return m["config"]

    def merge_rules(self, mapping_id: str, new_rules: list[dict[str, Any]]) -> MappingConfig:
        cfg = self.get_mapping_config(mapping_id)
        if cfg is None:
            raise ValueError(f"Mapping {mapping_id} not found")
        existing = {(r["word"].strip().lower()): r for r in cfg.rules}
        for r in new_rules:
            existing[r["word"].strip().lower()] = r
        cfg.rules = list(existing.values())
        self._mappings[mapping_id]["config"] = cfg
        return cfg

    def upsert_chunk(
        self,
        tenant_id: str,
        mapping_id: str,
        chunk_ref: str,
        chunk_text: str,
        category_slug: str,
        embedding,
        sem_embedding,
        community_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        key = (tenant_id, mapping_id, chunk_ref)
        self._chunks[key] = ChunkRecord(
            chunk_ref=chunk_ref,
            chunk_text=chunk_text,
            category_slug=category_slug,
            embedding=embedding,
            sem_embedding=sem_embedding,
            community_id=community_id,
            metadata=metadata or {},
        )

    def list_chunks(
        self, tenant_id: str, mapping_id: str, refs: list[str] | None = None,
        category_filter: str | None = None,
    ) -> list[ChunkRecord]:
        out: list[ChunkRecord] = []
        for (tid, mid, ref), rec in self._chunks.items():
            if tid != tenant_id or mid != mapping_id:
                continue
            if refs is not None and ref not in refs:
                continue
            if category_filter and rec.category_slug != category_filter:
                continue
            out.append(rec)
        return out

    def all_chunks(self, tenant_id: str, mapping_id: str) -> list[ChunkRecord]:
        return self.list_chunks(tenant_id, mapping_id)

    def set_edges(self, tenant_id: str, mapping_id: str, edges: list[GraphEdge]) -> None:
        self._edges[(tenant_id, mapping_id)] = list(edges)

    def get_edges(self, tenant_id: str, mapping_id: str) -> list[GraphEdge]:
        return list(self._edges.get((tenant_id, mapping_id), []))

    def add_edge(
        self, tenant_id: str, mapping_id: str,
        from_word: str, to_word: str, edge_type: str, weight: float,
    ) -> None:
        key = (tenant_id, mapping_id)
        self._edges.setdefault(key, []).append(
            GraphEdge(from_word, to_word, edge_type, weight)
        )

    def set_communities(
        self, tenant_id: str, mapping_id: str,
        summaries: list[CommunitySummary],
        members: dict[str, int],
    ) -> None:
        prefix = (tenant_id, mapping_id)
        for k in list(self._communities):
            if k[:2] == prefix:
                del self._communities[k]
        for k in list(self._members):
            if k[:2] == prefix:
                del self._members[k]
        for s in summaries:
            self._communities[(tenant_id, mapping_id, s.community_id)] = s
        for word, cid in members.items():
            self._members[(tenant_id, mapping_id, word)] = cid
        for (tid, mid, ref), rec in list(self._chunks.items()):
            if tid == tenant_id and mid == mapping_id:
                rec.community_id = members.get(ref)

    def list_communities(self, tenant_id: str, mapping_id: str) -> list[CommunitySummary]:
        return [
            v for k, v in self._communities.items()
            if k[0] == tenant_id and k[1] == mapping_id
        ]

    def get_community(self, tenant_id: str, mapping_id: str, community_id: int) -> CommunitySummary | None:
        return self._communities.get((tenant_id, mapping_id, community_id))

    def upsert_bridge(
        self, tenant_id: str, mapping_id: str,
        community_a: int, community_b: int, label: str,
        embedding, sem_embedding,
    ) -> BridgeRecord:
        bid = self._next_bridge_id
        self._next_bridge_id += 1
        rec = BridgeRecord(bid, community_a, community_b, label, embedding, sem_embedding)
        self._bridges[(tenant_id, mapping_id, community_a, community_b)] = rec
        return rec

    def list_bridges(self, tenant_id: str, mapping_id: str) -> list[BridgeRecord]:
        return [
            v for k, v in self._bridges.items()
            if k[0] == tenant_id and k[1] == mapping_id
        ]

    def create_job(self, tenant_id: str, source_type: str) -> str:
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = JobRecord(
            job_id=job_id,
            tenant_id=tenant_id,
            status=JobStatus.queued,
            source_type=source_type,
        )
        return job_id

    def update_job(self, job_id: str, **fields: Any) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        for k, v in fields.items():
            if hasattr(job, k):
                setattr(job, k, v)

    def get_job(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def job_to_dict(self, job: JobRecord) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "status": job.status.value,
            "source_type": job.source_type,
            "mapping_id": job.mapping_id,
            "records_total": job.records_total,
            "records_written": job.records_written,
            "progress_pct": job.progress_pct,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

    def save_mlp(self, tenant_id: str, mapping_id: str, blob: bytes) -> None:
        self._mlp_blobs[(tenant_id, mapping_id)] = blob

    def load_mlp(self, tenant_id: str, mapping_id: str) -> bytes | None:
        return self._mlp_blobs.get((tenant_id, mapping_id))
