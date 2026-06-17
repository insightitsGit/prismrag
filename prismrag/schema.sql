-- PrismRAG schema
-- Run once per environment. Idempotent (IF NOT EXISTS everywhere).
-- Requires pgvector extension.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE SCHEMA IF NOT EXISTS prismrag;

-- ── Tenant / client isolation ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.tenant (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    owner_email     VARCHAR(200),
    tier            VARCHAR(20)  NOT NULL DEFAULT 'tier1',  -- 'tier1' | 'tier2'
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ── Mapping definition (Tier 1: rules; Tier 2: MLP trained on rules) ──────────
CREATE TABLE IF NOT EXISTS prismrag.mapping_version (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    version         INT  NOT NULL DEFAULT 1,
    strategy        VARCHAR(30) NOT NULL DEFAULT 'rules',  -- 'rules'|'mlp'|'cluster'|'external_api'
    config_json     JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft|active|archived
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, version)
);

-- Category table — the explicit Tier-1 mapping (word → group)
CREATE TABLE IF NOT EXISTS prismrag.mapping_category (
    id              BIGSERIAL PRIMARY KEY,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id) ON DELETE CASCADE,
    category_slug   VARCHAR(100) NOT NULL,
    category_label  VARCHAR(200) NOT NULL,
    sort_order      INT NOT NULL DEFAULT 0,
    UNIQUE (mapping_id, category_slug)
);

-- Word→category assignments (the explicit mapping rows)
CREATE TABLE IF NOT EXISTS prismrag.mapping_rule (
    id              BIGSERIAL PRIMARY KEY,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id) ON DELETE CASCADE,
    word            VARCHAR(500) NOT NULL,
    category_slug   VARCHAR(100) NOT NULL,
    weight          FLOAT NOT NULL DEFAULT 1.0,
    source          VARCHAR(50) NOT NULL DEFAULT 'manual',  -- manual|sql|file|api
    UNIQUE (mapping_id, word)
);
CREATE INDEX IF NOT EXISTS ix_mapping_rule_mapping ON prismrag.mapping_rule (mapping_id);

-- ── Ingestion jobs ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.ingest_job (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id      UUID REFERENCES prismrag.mapping_version(id),
    source_type     VARCHAR(30) NOT NULL,  -- sql|file|api|chunk
    source_config   JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'queued',  -- queued|running|completed|failed|stale
    records_total   INT,
    records_written INT NOT NULL DEFAULT 0,
    progress_pct    INT NOT NULL DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    timeout_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ingest_job_tenant ON prismrag.ingest_job (tenant_id);

-- ── Semantic embedding cache (shared across tenants) ──────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.semantic_embedding (
    word            VARCHAR(500) NOT NULL,
    model           VARCHAR(80)  NOT NULL DEFAULT 'text-embedding-004',
    vec             VECTOR(768)  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (word, model)
);

-- ── Per-tenant chunk embeddings (the re-mapped personal vectors) ──────────────
-- This is the core output table — what clients query against.
CREATE TABLE IF NOT EXISTS prismrag.chunk_embedding (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id),
    chunk_text      TEXT NOT NULL,
    chunk_ref       VARCHAR(500),              -- source reference (table/row/url)
    category_slug   VARCHAR(100),              -- Tier-1 assigned category
    community_id    INT,                       -- Louvain community (after graph build)
    embedding       VECTOR(256)  NOT NULL,     -- personal MLP 256-d vector
    sem_embedding   VECTOR(768),               -- Gemini 768-d (kept for centroid search)
    metadata_json   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, mapping_id, chunk_ref)
);

-- HNSW index for fast cosine search (enterprise-scale)
CREATE INDEX IF NOT EXISTS ix_chunk_embedding_hnsw
    ON prismrag.chunk_embedding
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_chunk_embedding_sem_hnsw
    ON prismrag.chunk_embedding
    USING hnsw (sem_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_chunk_tenant_mapping
    ON prismrag.chunk_embedding (tenant_id, mapping_id);

CREATE INDEX IF NOT EXISTS ix_chunk_category
    ON prismrag.chunk_embedding (tenant_id, category_slug);

-- ── Word graph ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.word_graph_edge (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id  UUID NOT NULL REFERENCES prismrag.mapping_version(id),
    from_word   VARCHAR(500) NOT NULL,
    to_word     VARCHAR(500) NOT NULL,
    edge_type   VARCHAR(50)  NOT NULL DEFAULT 'rule',  -- rule|semantic|bridge
    weight      FLOAT        NOT NULL DEFAULT 1.0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, mapping_id, from_word, to_word, edge_type)
);
CREATE INDEX IF NOT EXISTS ix_wge_tenant_mapping ON prismrag.word_graph_edge (tenant_id, mapping_id);
CREATE INDEX IF NOT EXISTS ix_wge_from           ON prismrag.word_graph_edge (tenant_id, mapping_id, from_word);

-- ── Community tables ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.community_member (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id),
    word            VARCHAR(500) NOT NULL,
    community_id    INT  NOT NULL,
    centroid_vec    VECTOR(768),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, mapping_id, word)
);
CREATE INDEX IF NOT EXISTS ix_comm_member_tenant  ON prismrag.community_member (tenant_id, mapping_id);
CREATE INDEX IF NOT EXISTS ix_comm_member_cid     ON prismrag.community_member (tenant_id, mapping_id, community_id);
CREATE INDEX IF NOT EXISTS ix_comm_member_hnsw
    ON prismrag.community_member
    USING hnsw (centroid_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS prismrag.community_summary (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id),
    community_id    INT  NOT NULL,
    label           TEXT NOT NULL DEFAULT '',
    summary_text    TEXT NOT NULL DEFAULT '',
    category_slug   VARCHAR(100),              -- dominant Tier-1 category
    top_words       TEXT[] NOT NULL DEFAULT '{}',
    word_count      INT    NOT NULL DEFAULT 0,
    centroid_vec    VECTOR(768),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, mapping_id, community_id)
);
CREATE INDEX IF NOT EXISTS ix_comm_summary_tenant ON prismrag.community_summary (tenant_id, mapping_id);
CREATE INDEX IF NOT EXISTS ix_comm_summary_hnsw
    ON prismrag.community_summary
    USING hnsw (centroid_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── AP001.2: Bridge vectors ───────────────────────────────────────────────────
-- Synthetic connector nodes between two communities. Injected post-hoc.
CREATE TABLE IF NOT EXISTS prismrag.bridge_vector (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id),
    community_a     INT  NOT NULL,
    community_b     INT  NOT NULL,
    label           TEXT NOT NULL DEFAULT '',          -- LLM-generated bridge label
    embedding       VECTOR(256) NOT NULL,              -- midpoint in personal space
    sem_embedding   VECTOR(768),                       -- midpoint in semantic space
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, mapping_id, community_a, community_b)
);
CREATE INDEX IF NOT EXISTS ix_bridge_hnsw
    ON prismrag.bridge_vector
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── MLP model artifact (Tier 2) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.mlp_artifact (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES prismrag.tenant(id) ON DELETE CASCADE,
    mapping_id      UUID NOT NULL REFERENCES prismrag.mapping_version(id),
    weights_blob    BYTEA NOT NULL,
    embed_dim       INT   NOT NULL DEFAULT 256,
    recall_at_10    FLOAT,
    loss_final      FLOAT,
    epochs          INT,
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, mapping_id)
);
