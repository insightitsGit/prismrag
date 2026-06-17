"""PrismRAG — Pydantic request/response models."""
from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    sql   = "sql"
    file  = "file"
    api   = "api"
    chunk = "chunk"     # re-map existing pgvector chunk store


class StrategyType(str, Enum):
    rules        = "rules"         # Tier 1: explicit word→category table
    mlp          = "mlp"           # Tier 2: MLP trained on rules
    cluster      = "cluster"       # auto-cluster (K-means)
    external_api = "external_api"  # delegate to client's own model


class JobStatus(str, Enum):
    queued    = "queued"
    running   = "running"
    completed = "completed"
    failed    = "failed"
    stale     = "stale"


# ── Source configs ─────────────────────────────────────────────────────────────

class SQLSourceConfig(BaseModel):
    connection_string: str = Field(..., description="PostgreSQL DSN or SQLAlchemy URL")
    query: str             = Field(..., description="SELECT query returning (word, text) rows")
    word_column: str       = Field("word",  description="Column name for the word/token")
    text_column:  str      = Field("text",  description="Column name for the full chunk text")
    page_size: int         = Field(1000, ge=1, le=50000)


class FileSourceConfig(BaseModel):
    filename: str          = Field(..., description="Original filename (for logging)")
    word_column: str       = Field("word")
    text_column:  str      = Field("text")
    category_column: str | None = Field(None, description="Optional pre-assigned category column")


class APISourceConfig(BaseModel):
    url: str               = Field(..., description="Paginated REST endpoint URL")
    headers: dict[str, str] = Field(default_factory=dict)
    word_field: str        = Field("word")
    text_field:  str       = Field("text")
    page_param:  str       = Field("page")
    page_size:   int       = Field(500)


class ChunkSourceConfig(BaseModel):
    source_dsn: str        = Field(..., description="DSN of the existing pgvector database")
    source_table: str      = Field(..., description="Fully qualified table name e.g. public.chunks")
    text_column: str       = Field("content")
    ref_column:  str       = Field("id")
    where_clause: str      = Field("", description="Optional WHERE clause (no WHERE keyword)")


# ── Mapping / category ────────────────────────────────────────────────────────

class CategoryIn(BaseModel):
    slug:  str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    sort_order: int = Field(0)


class MappingRuleIn(BaseModel):
    word:          str   = Field(..., min_length=1)
    category_slug: str   = Field(..., min_length=1)
    weight:        float = Field(1.0, ge=0.0, le=10.0)


class MappingConfigIn(BaseModel):
    categories: list[CategoryIn]
    rules:      list[MappingRuleIn]


# ── Job request ───────────────────────────────────────────────────────────────

class JobRequest(BaseModel):
    tenant_id:   UUID
    source_type: SourceType
    strategy:    StrategyType = StrategyType.rules

    # Only one of these should be set based on source_type
    sql_config:  SQLSourceConfig  | None = None
    file_config: FileSourceConfig | None = None
    api_config:  APISourceConfig  | None = None
    chunk_config:ChunkSourceConfig| None = None

    # Tier-1 mapping (required for rules/mlp strategies)
    mapping: MappingConfigIn | None = None

    # Tier-2 MLP options (strategy='mlp')
    mlp_epochs: int | None = None
    mlp_recall_target: float | None = None

    webhook_url: str | None = Field(None, description="Called when job completes")


class JobResponse(BaseModel):
    job_id:     str
    tenant_id:  str
    status:     JobStatus
    status_url: str
    sync:       bool = Field(False, description="True if completed inline (small dataset)")


class JobStatusResponse(BaseModel):
    job_id:          str
    tenant_id:       str
    status:          JobStatus
    records_total:   int | None
    records_written: int
    progress_pct:    int
    error_message:   str | None
    started_at:      str | None
    finished_at:     str | None


# ── Search / serve ────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    tenant_id:  UUID
    mapping_id: UUID | None = None     # defaults to latest active mapping
    query:      str  = Field(..., min_length=1)
    top_k:      int  = Field(10, ge=1, le=100)
    category_filter: str | None = None


class SearchHit(BaseModel):
    chunk_text:    str
    chunk_ref:     str | None
    category_slug: str | None
    community_id:  int | None
    community_label: str | None
    score:         float
    metadata:      dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query:        str
    tenant_id:    str
    mapping_id:   str
    retrieval_mode: str          # 'graph_rag' | 'direct'
    hits:         list[SearchHit]
    communities:  list[dict[str, Any]] = Field(default_factory=list)


# ── Bridge vector (AP001.2) ───────────────────────────────────────────────────

class BridgeRequest(BaseModel):
    tenant_id:    UUID
    mapping_id:   UUID
    community_a:  int = Field(..., description="Source community ID")
    community_b:  int = Field(..., description="Target community ID")
    label:        str | None = Field(None, description="Override auto-generated label")


class BridgeResponse(BaseModel):
    bridge_id:    int
    tenant_id:    str
    mapping_id:   str
    community_a:  int
    community_b:  int
    label:        str
