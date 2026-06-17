-- Finance QA Domain Seed Data
-- Tenant: qa-finance | Mapping: finance-standard
-- Run after schema.sql

BEGIN;

-- ── QA Tenant ─────────────────────────────────────────────────────────────────
INSERT INTO prismrag.tenant (id, name, plan, owner_user_id)
VALUES ('10000000-0000-0000-0000-000000000003', 'QA FinanceCo', 'professional', '20000000-0000-0000-0000-000000000003')
ON CONFLICT (id) DO NOTHING;

-- ── Mapping ────────────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping (id, tenant_id, name, strategy, version, is_active)
VALUES ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000003', 'finance-standard', 'rules', 1, true)
ON CONFLICT (id) DO NOTHING;

-- ── Categories ────────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping_category (mapping_id, category_slug, category_label, sort_order) VALUES
('30000000-0000-0000-0000-000000000003', 'risk',            'Risk & Compliance',         1),
('30000000-0000-0000-0000-000000000003', 'growth',          'Growth & Opportunity',      2),
('30000000-0000-0000-0000-000000000003', 'valuation',       'Valuation & Pricing',       3),
('30000000-0000-0000-0000-000000000003', 'liquidity',       'Liquidity & Cash Flow',     4),
('30000000-0000-0000-0000-000000000003', 'debt',            'Debt & Capital Structure',  5),
('30000000-0000-0000-0000-000000000003', 'market_analysis', 'Market Analysis',           6),
('30000000-0000-0000-0000-000000000003', 'regulatory',      'Regulatory & Reporting',    7)
ON CONFLICT DO NOTHING;

-- ── Mapping Rules ─────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping_rule (mapping_id, word, category_slug, weight) VALUES
-- Risk
('30000000-0000-0000-0000-000000000003', 'volatility',           'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'var',                  'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'credit_risk',          'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'market_risk',          'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'operational_risk',     'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'beta',                 'risk',          0.9),
('30000000-0000-0000-0000-000000000003', 'drawdown',             'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'stress_test',          'risk',          1.0),
('30000000-0000-0000-0000-000000000003', 'default_probability',  'risk',          1.0),
-- Growth
('30000000-0000-0000-0000-000000000003', 'alpha',                'growth',        1.0),
('30000000-0000-0000-0000-000000000003', 'revenue_growth',       'growth',        1.0),
('30000000-0000-0000-0000-000000000003', 'ebitda_growth',        'growth',        1.0),
('30000000-0000-0000-0000-000000000003', 'market_share',         'growth',        1.0),
('30000000-0000-0000-0000-000000000003', 'cagr',                 'growth',        1.0),
('30000000-0000-0000-0000-000000000003', 'expansion',            'growth',        0.8),
('30000000-0000-0000-0000-000000000003', 'acquisition_target',   'growth',        0.9),
-- Valuation
('30000000-0000-0000-0000-000000000003', 'dcf',                  'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'ebitda',               'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'pe_ratio',             'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'ev_ebitda',            'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'wacc',                 'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'terminal_value',       'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'fair_value',           'valuation',     1.0),
('30000000-0000-0000-0000-000000000003', 'book_value',           'valuation',     0.9),
-- Liquidity
('30000000-0000-0000-0000-000000000003', 'current_ratio',        'liquidity',     1.0),
('30000000-0000-0000-0000-000000000003', 'quick_ratio',          'liquidity',     1.0),
('30000000-0000-0000-0000-000000000003', 'free_cash_flow',       'liquidity',     1.0),
('30000000-0000-0000-0000-000000000003', 'operating_cash_flow',  'liquidity',     1.0),
('30000000-0000-0000-0000-000000000003', 'working_capital',      'liquidity',     1.0),
('30000000-0000-0000-0000-000000000003', 'burn_rate',            'liquidity',     1.0),
-- Debt
('30000000-0000-0000-0000-000000000003', 'leverage_ratio',       'debt',          1.0),
('30000000-0000-0000-0000-000000000003', 'debt_to_equity',       'debt',          1.0),
('30000000-0000-0000-0000-000000000003', 'interest_coverage',    'debt',          1.0),
('30000000-0000-0000-0000-000000000003', 'covenant',             'debt',          1.0),
('30000000-0000-0000-0000-000000000003', 'bond_yield',           'debt',          1.0),
('30000000-0000-0000-0000-000000000003', 'credit_rating',        'debt',          1.0),
('30000000-0000-0000-0000-000000000003', 'refinancing',          'debt',          0.9),
-- Market Analysis
('30000000-0000-0000-0000-000000000003', 'total_addressable_market','market_analysis',1.0),
('30000000-0000-0000-0000-000000000003', 'competitive_moat',     'market_analysis',1.0),
('30000000-0000-0000-0000-000000000003', 'pricing_power',        'market_analysis',1.0),
('30000000-0000-0000-0000-000000000003', 'industry_cycle',       'market_analysis',1.0),
('30000000-0000-0000-0000-000000000003', 'market_concentration', 'market_analysis',1.0),
-- Regulatory
('30000000-0000-0000-0000-000000000003', 'sec_filing',           'regulatory',    1.0),
('30000000-0000-0000-0000-000000000003', 'ifrs',                 'regulatory',    1.0),
('30000000-0000-0000-0000-000000000003', 'gaap',                 'regulatory',    1.0),
('30000000-0000-0000-0000-000000000003', 'aml',                  'regulatory',    1.0),
('30000000-0000-0000-0000-000000000003', 'kyc',                  'regulatory',    1.0),
('30000000-0000-0000-0000-000000000003', 'sox_compliance',       'regulatory',    1.0),
('30000000-0000-0000-0000-000000000003', 'capital_adequacy',     'regulatory',    1.0)
ON CONFLICT DO NOTHING;

-- ── Sample knowledge chunks ───────────────────────────────────────────────────
INSERT INTO prismrag.chunk (id, tenant_id, mapping_id, chunk_ref, source_ref, text_snippet, category_slug) VALUES
('40000000-0000-0000-0000-000000000301', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-001', 'analyst-reports', 'Portfolio VaR at 95% confidence interval is $2.4M over 1-day horizon. Beta 1.32 indicates above-market volatility. Stress test under 2008 scenario shows 34% drawdown.', 'risk'),
('40000000-0000-0000-0000-000000000302', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-002', 'analyst-reports', 'Revenue CAGR of 22% over 3 years driven by SaaS segment expansion. Alpha generation of 4.2% above benchmark. Market share increased to 14% in core segment.', 'growth'),
('40000000-0000-0000-0000-000000000303', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-003', 'analyst-reports', 'DCF valuation: WACC 9.2%, terminal growth 3.0%, EV/EBITDA 14.5x at current prices. Fair value $47 per share vs. current price $38. P/E ratio 22x on FY25 estimates.', 'valuation'),
('40000000-0000-0000-0000-000000000304', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-004', 'analyst-reports', 'Free cash flow $180M vs. $145M prior year. Current ratio 2.1, quick ratio 1.8. Working capital position strong. Burn rate $12M/month in growth segment — 18-month runway.', 'liquidity'),
('40000000-0000-0000-0000-000000000305', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-005', 'analyst-reports', 'Debt-to-equity ratio 0.45, interest coverage 8.2x. Senior notes rated BBB+ by S&P. Covenant threshold: net leverage below 3.5x. Refinancing opportunity at current spreads.', 'debt'),
('40000000-0000-0000-0000-000000000306', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-006', 'analyst-reports', 'TAM estimated $42B growing at 18% annually. Competitive moat via network effects and switching costs. Pricing power demonstrated: 12% price increase with <5% churn.', 'market_analysis'),
('40000000-0000-0000-0000-000000000307', '10000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000003',
 'fn-chunk-007', 'analyst-reports', 'SOX 404 audit completed with no material weaknesses. GAAP to IFRS reconciliation shows $3.2M timing difference on revenue recognition. AML program reviewed — no SAR filings.', 'regulatory')
ON CONFLICT DO NOTHING;

COMMIT;
