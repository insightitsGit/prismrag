-- PrismRAG — Deliberation schema
-- Horizontal → Vertical → Synthesis pipeline

CREATE TABLE IF NOT EXISTS prismrag.deliberation_session (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        REFERENCES prismrag.user_account(id) ON DELETE SET NULL,
    tenant_id       UUID,                           -- optional: scoped to a PrismRAG workspace
    title           VARCHAR(500),
    status          VARCHAR(30) NOT NULL DEFAULT 'created',
    -- status: created | discovering | querying | synthesizing | done | failed
    question        TEXT        NOT NULL,
    domain_count    SMALLINT    NOT NULL DEFAULT 7,  -- how many domains to discover
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '30 days'
);
CREATE INDEX IF NOT EXISTS ix_ds_user ON prismrag.deliberation_session (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_ds_status ON prismrag.deliberation_session (status, created_at DESC);

-- Discovered domains from horizontal search
CREATE TABLE IF NOT EXISTS prismrag.deliberation_domain (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID        NOT NULL REFERENCES prismrag.deliberation_session(id) ON DELETE CASCADE,
    rank            SMALLINT    NOT NULL,            -- 1 = most relevant
    name            VARCHAR(200) NOT NULL,           -- e.g. "Behavioral Economics"
    slug            VARCHAR(100) NOT NULL,           -- e.g. "behavioral_economics"
    relevance_score FLOAT       NOT NULL DEFAULT 0,
    rationale       TEXT,                           -- why this domain is relevant
    source          VARCHAR(30) NOT NULL DEFAULT 'llm',  -- llm | kb | hybrid
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dd_session ON prismrag.deliberation_domain (session_id, rank);

-- Vertical query results per domain
CREATE TABLE IF NOT EXISTS prismrag.deliberation_vertical (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID        NOT NULL REFERENCES prismrag.deliberation_session(id) ON DELETE CASCADE,
    domain_id       UUID        NOT NULL REFERENCES prismrag.deliberation_domain(id) ON DELETE CASCADE,
    query_text      TEXT        NOT NULL,            -- the targeted query sent for this domain
    findings        TEXT        NOT NULL,            -- domain expert's response
    kb_hits         JSONB,                          -- PrismRAG search results if tenant_id set
    confidence      FLOAT       NOT NULL DEFAULT 0, -- 0-1 model confidence estimate
    tokens_used     INT,
    latency_ms      INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dv_session ON prismrag.deliberation_vertical (session_id);

-- Final deliberation synthesis
CREATE TABLE IF NOT EXISTS prismrag.deliberation_synthesis (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID        NOT NULL REFERENCES prismrag.deliberation_session(id) ON DELETE CASCADE,
    synthesis_type  VARCHAR(30) NOT NULL DEFAULT 'comparison',
    -- synthesis_type: comparison | consensus | conflict | comprehensive
    agreements      TEXT,       -- where domains converge
    conflicts       TEXT,       -- where domains diverge
    unique_insights TEXT,       -- domain-specific insights not shared elsewhere
    final_answer    TEXT        NOT NULL,
    confidence      FLOAT       NOT NULL DEFAULT 0,
    contributing_domains JSONB, -- [{name, weight, agreement_score}]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dsynth_session ON prismrag.deliberation_synthesis (session_id);

-- Follow-up turns on a session
CREATE TABLE IF NOT EXISTS prismrag.deliberation_followup (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID        NOT NULL REFERENCES prismrag.deliberation_session(id) ON DELETE CASCADE,
    question        TEXT        NOT NULL,
    answer          TEXT,
    domains_used    JSONB,      -- subset of original domains re-activated for this followup
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dfu_session ON prismrag.deliberation_followup (session_id, created_at);
