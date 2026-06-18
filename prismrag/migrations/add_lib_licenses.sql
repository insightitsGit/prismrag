-- PrismRAG Patch library license management
-- Applied by: python scripts/init_azure_schema.py

CREATE TABLE IF NOT EXISTS prismrag.lib_license (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_key_hash      VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 of the raw key
    license_key_prefix    VARCHAR(16) NOT NULL,          -- e.g. "prlib_a1b2c3d4" (first 16 chars, safe to display)
    company_name          VARCHAR(200) NOT NULL,
    contact_email         VARCHAR(200) NOT NULL,
    plan                  VARCHAR(20) NOT NULL DEFAULT 'annual',  -- annual | monthly | enterprise
    status                VARCHAR(20) NOT NULL DEFAULT 'active',  -- active | expired | suspended | cancelled
    issued_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at            TIMESTAMPTZ NOT NULL,
    max_calls_per_day     INT NOT NULL DEFAULT 500000,
    stripe_subscription_id VARCHAR(200),
    stripe_customer_id    VARCHAR(200),
    last_validated_at     TIMESTAMPTZ,
    calls_today           INT NOT NULL DEFAULT 0,
    calls_reset_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_lib_license_hash   ON prismrag.lib_license (license_key_hash);
CREATE INDEX IF NOT EXISTS ix_lib_license_email  ON prismrag.lib_license (contact_email);
CREATE INDEX IF NOT EXISTS ix_lib_license_status ON prismrag.lib_license (status);
