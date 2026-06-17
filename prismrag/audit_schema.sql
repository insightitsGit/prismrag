-- PrismRAG — Audit + output storage schema
-- Run after schema.sql and auth_schema.sql

-- ── API request log ────────────────────────────────────────────────────────────
-- One row per API call. Written async — never blocks responses.
-- Retention controlled by plan: free=7d, starter/professional=30d, enterprise=90d.
-- Cleanup job in prismrag/worker/cleanup.py runs nightly via cron.

CREATE TABLE IF NOT EXISTS prismrag.api_request_log (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         TEXT,                           -- UUID or "apikey:<hash>" or NULL
    plan            VARCHAR(30)     NOT NULL DEFAULT 'anonymous',
    method          VARCHAR(10)     NOT NULL,
    path            VARCHAR(500)    NOT NULL,
    query_string    TEXT            NOT NULL DEFAULT '',
    status_code     SMALLINT        NOT NULL,
    latency_ms      INT             NOT NULL,
    req_body        TEXT            NOT NULL DEFAULT '',   -- sanitized, 8 KB max
    resp_body       TEXT            NOT NULL DEFAULT '',   -- truncated, 4 KB max
    client_ip       VARCHAR(45)     NOT NULL DEFAULT '',
    user_agent      VARCHAR(200)    NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- Fast lookup by user + time (dashboard "recent calls")
CREATE INDEX IF NOT EXISTS ix_log_user_time
    ON prismrag.api_request_log (user_id, created_at DESC);

-- Cleanup target: scan by created_at
CREATE INDEX IF NOT EXISTS ix_log_created
    ON prismrag.api_request_log (created_at);

-- Fast status-code analytics (error rate dashboards)
CREATE INDEX IF NOT EXISTS ix_log_status
    ON prismrag.api_request_log (status_code, created_at DESC);


-- ── Search result cache (stored outputs) ─────────────────────────────────────
-- Stores the actual results returned to users so they can:
--   1. Replay a query without re-embedding
--   2. Audit what the system returned at a given point in time
--   3. Debug retrieval quality issues
-- TTL enforced by cleanup job. Enterprise gets 90d, others 30d.

CREATE TABLE IF NOT EXISTS prismrag.search_result_log (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            REFERENCES prismrag.user_account(id) ON DELETE SET NULL,
    tenant_id       UUID,
    mapping_id      UUID,
    query_text      TEXT            NOT NULL,
    query_embedding VECTOR(768),                    -- stored so we can re-rank later
    top_k           SMALLINT        NOT NULL DEFAULT 10,
    category_filter VARCHAR(100),
    results         JSONB           NOT NULL,        -- full SearchResponse as JSON
    retrieval_mode  VARCHAR(30)     NOT NULL DEFAULT 'graph_rag',  -- graph_rag|direct_hnsw
    latency_ms      INT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ     NOT NULL         -- set by API based on plan
);

CREATE INDEX IF NOT EXISTS ix_srl_user_time
    ON prismrag.search_result_log (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_srl_expires
    ON prismrag.search_result_log (expires_at);

-- Allow re-running the same query ("replay last search")
CREATE INDEX IF NOT EXISTS ix_srl_query_tenant
    ON prismrag.search_result_log (tenant_id, query_text, created_at DESC);


-- ── Ingest job output log ──────────────────────────────────────────────────────
-- Stores a summary of every completed ingest job (not raw data — just metadata
-- and sample). Full chunk data lives in chunk_embedding.

CREATE TABLE IF NOT EXISTS prismrag.ingest_result_log (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          TEXT            NOT NULL,
    user_id         UUID            REFERENCES prismrag.user_account(id) ON DELETE SET NULL,
    tenant_id       UUID,
    mapping_id      UUID,
    strategy        VARCHAR(30),
    records_total   INT,
    records_written INT,
    records_failed  INT             NOT NULL DEFAULT 0,
    mlp_val_recall  FLOAT,          -- NULL for Tier-1 jobs
    community_count INT,
    duration_s      INT,
    error_summary   TEXT,           -- first 2 KB of any error
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ     NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_irl_user_time
    ON prismrag.ingest_result_log (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_irl_expires
    ON prismrag.ingest_result_log (expires_at);


-- ── Large-file upload registry ─────────────────────────────────────────────────
-- Tracks files uploaded via Azure Blob Storage presigned URL.
-- Status: pending_upload → uploaded → processing → done | failed

CREATE TABLE IF NOT EXISTS prismrag.large_file_upload (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES prismrag.user_account(id) ON DELETE CASCADE,
    tenant_id       UUID            NOT NULL,
    blob_url        TEXT            NOT NULL,        -- Azure Blob Storage URL (no SAS token stored)
    blob_container  VARCHAR(200)    NOT NULL,
    blob_name       VARCHAR(500)    NOT NULL,
    file_size_bytes BIGINT,
    original_name   VARCHAR(500),
    status          VARCHAR(30)     NOT NULL DEFAULT 'pending_upload',
    job_id          TEXT,                           -- linked once worker picks it up
    sas_expires_at  TIMESTAMPTZ,                   -- when the upload SAS token expires
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_lfu_user ON prismrag.large_file_upload (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_lfu_status ON prismrag.large_file_upload (status, created_at);
