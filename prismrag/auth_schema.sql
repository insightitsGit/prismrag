-- PrismRAG — Auth + Billing schema (append to schema.sql or run separately)

-- ── User accounts ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.user_account (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(320) NOT NULL UNIQUE,
    password_hash   TEXT         NOT NULL,
    full_name       VARCHAR(200) NOT NULL DEFAULT '',
    company         VARCHAR(200) NOT NULL DEFAULT '',
    plan            VARCHAR(30)  NOT NULL DEFAULT 'free',     -- free|starter|professional|enterprise
    stripe_customer_id    VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    subscription_status   VARCHAR(30) NOT NULL DEFAULT 'inactive', -- inactive|active|past_due|canceled
    subscription_period_end TIMESTAMPTZ,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_email ON prismrag.user_account (email);
CREATE INDEX IF NOT EXISTS ix_user_stripe_customer ON prismrag.user_account (stripe_customer_id);

-- ── API keys (users can have multiple) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.api_key (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES prismrag.user_account(id) ON DELETE CASCADE,
    key_hash        TEXT NOT NULL UNIQUE,           -- SHA-256 of the raw key
    key_prefix      VARCHAR(12) NOT NULL,           -- first 12 chars shown in UI
    label           VARCHAR(100) NOT NULL DEFAULT 'Default',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_key_hash   ON prismrag.api_key (key_hash);
CREATE INDEX IF NOT EXISTS ix_api_key_user   ON prismrag.api_key (user_id);

-- ── Plan quotas ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.plan_quota (
    plan            VARCHAR(30) PRIMARY KEY,
    monthly_chunks  INT         NOT NULL DEFAULT 0,    -- 0 = unlimited
    max_tenants     INT         NOT NULL DEFAULT 1,
    max_mappings    INT         NOT NULL DEFAULT 1,
    tier2_mlp       BOOLEAN     NOT NULL DEFAULT FALSE,
    graph_rag       BOOLEAN     NOT NULL DEFAULT FALSE,
    bridge_vectors  BOOLEAN     NOT NULL DEFAULT FALSE,
    support_level   VARCHAR(30) NOT NULL DEFAULT 'community'
);

INSERT INTO prismrag.plan_quota VALUES
    ('free',         5000,   1,  1, FALSE, FALSE, FALSE, 'community'),
    ('starter',     50000,   1,  3, FALSE,  TRUE, FALSE, 'email'),
    ('professional',500000, 10, 20,  TRUE,  TRUE,  TRUE, 'priority'),
    ('enterprise',       0, -1, -1,  TRUE,  TRUE,  TRUE, 'dedicated')
ON CONFLICT (plan) DO UPDATE SET
    monthly_chunks  = EXCLUDED.monthly_chunks,
    max_tenants     = EXCLUDED.max_tenants,
    tier2_mlp       = EXCLUDED.tier2_mlp,
    graph_rag       = EXCLUDED.graph_rag,
    bridge_vectors  = EXCLUDED.bridge_vectors;

-- ── Usage events (per API call) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prismrag.usage_event (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES prismrag.user_account(id) ON DELETE CASCADE,
    tenant_id       UUID,
    event_type      VARCHAR(50) NOT NULL,   -- ingest_chunk|search|bridge_create
    units           INT  NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_usage_user_month ON prismrag.usage_event (user_id, created_at);
