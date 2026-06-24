"""Store protocol — implemented by MemoryStore and PostgresStore."""
from __future__ import annotations

from typing import Any, Protocol

from prismrag_patch.models import JobStatus, MappingConfig
from prismrag_patch.store.types import (
    BridgeRecord,
    ChunkRecord,
    CommunitySummary,
    GraphEdge,
    JobRecord,
)


class Store(Protocol):
    def persist_mapping(
        self, tenant_id: str, mapping: MappingConfig, strategy: str = "rules"
    ) -> str: ...

    def latest_mapping(self, tenant_id: str) -> str | None: ...

    def get_mapping_config(self, mapping_id: str) -> MappingConfig | None: ...

    def merge_rules(self, mapping_id: str, new_rules: list[dict[str, Any]]) -> MappingConfig: ...

    def upsert_chunk(
        self,
        tenant_id: str,
        mapping_id: str,
        chunk_ref: str,
        chunk_text: str,
        category_slug: str,
        embedding: Any,
        sem_embedding: Any,
        community_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def list_chunks(
        self,
        tenant_id: str,
        mapping_id: str,
        refs: list[str] | None = None,
        category_filter: str | None = None,
    ) -> list[ChunkRecord]: ...

    def all_chunks(self, tenant_id: str, mapping_id: str) -> list[ChunkRecord]: ...

    def set_edges(self, tenant_id: str, mapping_id: str, edges: list[GraphEdge]) -> None: ...

    def get_edges(self, tenant_id: str, mapping_id: str) -> list[GraphEdge]: ...

    def add_edge(
        self,
        tenant_id: str,
        mapping_id: str,
        from_word: str,
        to_word: str,
        edge_type: str,
        weight: float,
    ) -> None: ...

    def set_communities(
        self,
        tenant_id: str,
        mapping_id: str,
        summaries: list[CommunitySummary],
        members: dict[str, int],
    ) -> None: ...

    def list_communities(self, tenant_id: str, mapping_id: str) -> list[CommunitySummary]: ...

    def get_community(
        self, tenant_id: str, mapping_id: str, community_id: int
    ) -> CommunitySummary | None: ...

    def upsert_bridge(
        self,
        tenant_id: str,
        mapping_id: str,
        community_a: int,
        community_b: int,
        label: str,
        embedding: Any,
        sem_embedding: Any,
    ) -> BridgeRecord: ...

    def list_bridges(self, tenant_id: str, mapping_id: str) -> list[BridgeRecord]: ...

    def create_job(self, tenant_id: str, source_type: str) -> str: ...

    def update_job(self, job_id: str, **fields: Any) -> None: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

    def job_to_dict(self, job: JobRecord) -> dict[str, Any]: ...

    def save_mlp(self, tenant_id: str, mapping_id: str, blob: bytes) -> None: ...

    def load_mlp(self, tenant_id: str, mapping_id: str) -> bytes | None: ...
