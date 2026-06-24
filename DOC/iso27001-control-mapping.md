# PrismRAG — ISO/IEC 27001:2022 Control Mapping

> **Note (2026):** Maps **legacy hosted SaaS** features. For pip-only deployments, map controls to your Postgres / cloud environment. See [INFO.md](../INFO.md).

This checklist maps **ISO 27001 Annex A controls** to **PrismRAG product features and operational evidence**. Use it for gap analysis before Stage 1 / Stage 2 audits.

**Legend**

| Status | Meaning |
|--------|---------|
| ✅ | Implemented in product or documented process |
| 🟡 | Partial — needs policy, ops, or hardening |
| ❌ | Not implemented — organizational or product gap |
| 📋 | Evidence to collect for auditor |

**Scope suggestion:** PrismRAG SaaS API, Postgres data store, Azure blob uploads (if used), auth/billing subsystems, and supporting cloud infrastructure.

---

## A.5 Organizational controls

| Control | Title | PrismRAG mapping | Status | Evidence / notes |
|---------|-------|------------------|--------|------------------|
| A.5.1 | Policies for information security | Not in repo | ❌ | 📋 Written ISMS policy, approved by management |
| A.5.2 | Information security roles | RBAC: `tenant_member` roles (`owner/admin/member/viewer`) | 🟡 | 📋 RACI matrix; who is CISO / DPO |
| A.5.3 | Segregation of duties | API key scopes (`read`/`write`); role separation per workspace | 🟡 | 📋 No single person prod+audit without review |
| A.5.4 | Management responsibilities | N/A (org) | ❌ | 📋 Management review minutes |
| A.5.5 | Contact with authorities | N/A (org) | ❌ | 📋 Incident notification procedure |
| A.5.6 | Contact with special interest groups | N/A (org) | ❌ | Optional |
| A.5.7 | Threat intelligence | N/A (org) | ❌ | 📋 CVE monitoring process for dependencies |
| A.5.8 | Info security in project management | Validation layer, enterprise schema migrations | 🟡 | 📋 SDLC security checklist in PRs |
| A.5.9 | Inventory of information assets | Tenant data in Postgres; mappings, embeddings, audit logs | 🟡 | 📋 Asset register: DB, blobs, API keys |
| A.5.10 | Acceptable use | Terms of service (`web/terms.html`) | 🟡 | 📋 Employee AUP document |
| A.5.11 | Return of assets | Tenant delete API | 🟡 | 📋 Offboarding checklist |
| A.5.12 | Classification of information | Plan-based retention; tenant isolation | 🟡 | 📋 Data classification policy |
| A.5.13 | Labelling of information | `category_slug` on chunks; tenant_id on all rows | 🟡 | Internal labels only |
| A.5.14 | Information transfer | TLS in transit; SAS upload direct to Azure | 🟡 | 📋 TLS config, cipher policy |
| A.5.15 | Access control | JWT + API keys + OIDC; `assert_tenant_access` / RBAC | ✅ | `prismrag/auth/`, `prismrag/auth/rbac.py` |
| A.5.16 | Identity management | `user_account`, `oidc_identity`, registration | 🟡 | 📋 No MFA yet |
| A.5.17 | Authentication information | bcrypt/PBKDF2 passwords; `prk_` API keys (hash only stored) | 🟡 | 📋 MFA, key rotation policy |
| A.5.18 | Access rights | RBAC + API key revoke; member invite/remove | ✅ | `tenant_routes.py`, `auth_routes.py` |
| A.5.19 | Supplier relationships | Stripe, Gemini, Azure, hosting | 🟡 | 📋 Vendor risk assessments (DPAs) |
| A.5.20 | Addressing security in supplier agreements | N/A (legal) | ❌ | 📋 DPAs with Google, Stripe, Azure |
| A.5.21 | ICT supply chain | `requirements.txt`, Docker images | 🟡 | 📋 SBOM, dependency scanning in CI |
| A.5.22 | Monitoring & review of supplier services | Stripe webhooks; usage metering | 🟡 | 📋 Quarterly vendor review |
| A.5.23 | Cloud services security | Multi-tenant SaaS; env-based secrets | 🟡 | 📋 Cloud shared responsibility doc |
| A.5.24 | Incident management planning | HTTP audit logs; job/search failure logs | 🟡 | 📋 IR runbook, on-call |
| A.5.25 | Assessment of events | `api_request_log`, `ingest_result_log`, `search_result_log` | 🟡 | 📋 Alerting on error rate |
| A.5.26 | Response to incidents | N/A (org) | ❌ | 📋 IR playbooks |
| A.5.27 | Learning from incidents | N/A (org) | ❌ | 📋 Post-incident reviews |
| A.5.28 | Collection of evidence | Audit tables + `trace_id` on requests | ✅ | `audit_schema.sql`, `middleware/logging.py` |
| A.5.29 | Information security during disruption | Job queue + worker; failed job retry | 🟡 | 📋 BCP/DR test records |
| A.5.30 | ICT readiness for business continuity | Postgres backups (ops) | 🟡 | 📋 RTO/RPO, restore drills |
| A.5.31 | Legal requirements | Privacy + Terms pages | 🟡 | 📋 GDPR/CCPA assessment |
| A.5.32 | Intellectual property rights | Customer owns uploaded content (Terms) | 🟡 | 📋 |
| A.5.33 | Protection of records | Audit log retention by plan | ✅ | `plan_quota.log_retention_days`, `worker/cleanup.py` |
| A.5.34 | Privacy and PII protection | Per-tenant isolation; export API | 🟡 | 📋 GDPR delete workflow; no DPA automation |
| A.5.35 | Independent review | N/A (org) | ❌ | 📋 Internal audit program |
| A.5.36 | Compliance with policies | Metering, validation, plan gates | 🟡 | 📋 |
| A.5.37 | Documented operating procedures | `DOC/`, `run-local.bat`, deployment docs | 🟡 | 📋 Runbooks for prod |

---

## A.6 People controls

| Control | Title | Status | Notes |
|---------|-------|--------|-------|
| A.6.1 | Screening | ❌ | 📋 Background checks for prod access |
| A.6.2 | Terms and conditions of employment | ❌ | 📋 Confidentiality in employment contracts |
| A.6.3 | Awareness, education and training | ❌ | 📋 Annual security training |
| A.6.4 | Disciplinary process | ❌ | 📋 HR policy |
| A.6.5 | Responsibilities after termination | 🟡 | API key revoke; remove `tenant_member` |
| A.6.6 | Confidentiality agreements | ❌ | 📋 NDAs |
| A.6.7 | Remote working | ❌ | 📋 Remote access policy |
| A.6.8 | Event reporting | 🟡 | 📋 security@ email + incident form |

---

## A.7 Physical controls

| Control | Title | Status | Notes |
|---------|-------|--------|-------|
| A.7.1–A.7.14 | Physical security | 🟡 | Delegated to cloud provider (Azure/AWS) + 📋 SOC 2 report from host |

---

## A.8 Technological controls

| Control | Title | PrismRAG mapping | Status | Evidence |
|---------|-------|------------------|--------|----------|
| A.8.1 | User endpoint devices | N/A (customer) | — | |
| A.8.2 | Privileged access rights | No admin UI; DB access ops-only | 🟡 | 📋 Break-glass DB access log |
| A.8.3 | Information access restriction | Tenant isolation + RBAC on every route | ✅ | `auth/tenant.py`, `auth/rbac.py` |
| A.8.4 | Access to source code | GitHub private repo (org) | 🟡 | 📋 Branch protection, CODEOWNERS |
| A.8.5 | Secure authentication | JWT, API keys, OIDC option | 🟡 | 📋 MFA not implemented |
| A.8.6 | Capacity management | Job queue, thread pool, worker process | ✅ | `tasks/dispatch.py`, `worker/job_worker.py` |
| A.8.7 | Protection against malware | N/A at app layer | 🟡 | 📋 Container scanning |
| A.8.8 | Management of technical vulnerabilities | Dependencies in `requirements.txt` | 🟡 | 📋 Dependabot/Snyk, pen test |
| A.8.9 | Configuration management | `.env`, `config.py`, schema SQL | 🟡 | 📋 IaC (Bicep), secrets in vault |
| A.8.10 | Information deletion | `DELETE /api/v1/tenants/{id}` CASCADE | ✅ | `tenant_routes.py`, `schema.sql` FK cascades |
| A.8.11 | Data masking | Passwords stripped from audit logs | ✅ | `middleware/logging.py` `_STRIP_FIELDS` |
| A.8.12 | Data leakage prevention | No raw API keys after creation; response suppression on login | ✅ | `auth_routes.py`, audit middleware |
| A.8.13 | Information backup | Postgres (ops) | 🟡 | 📋 Automated backups, restore test |
| A.8.14 | Redundancy | Single-process default locally | 🟡 | 📋 Multi-replica API + workers in prod |
| A.8.15 | Logging | `api_request_log`, result logs, Prometheus | ✅ | `audit_schema.sql`, `/metrics` |
| A.8.16 | Monitoring activities | Prometheus metrics, audit middleware | 🟡 | 📋 Alerting (PagerDuty/Datadog) |
| A.8.17 | Clock synchronization | Postgres `timestamptz`, UTC in jobs | ✅ | |
| A.8.18 | Use of privileged utility programs | N/A | — | |
| A.8.19 | Installation of software on operational systems | Docker / `run-local.bat` | 🟡 | 📋 Immutable deployments |
| A.8.20 | Networks security | CORS env config; TLS termination at proxy | 🟡 | 📋 WAF, private networking |
| A.8.21 | Security of network services | Rate limiting (Redis optional) | 🟡 | `metering/quota.py` |
| A.8.22 | Segregation of networks | Tenant logical isolation in DB | 🟡 | 📋 VPC per enterprise tier |
| A.8.23 | Web filtering | N/A | — | |
| A.8.24 | Use of cryptography | bcrypt, SHA-256 API keys, JWT HS256, TLS | 🟡 | 📋 Key rotation; consider RS256 |
| A.8.25 | Secure development life cycle | Pydantic validation, tests | 🟡 | 📋 SAST in CI, security review |
| A.8.26 | Application security requirements | Input validation (`validation.py`, `models.py`) | ✅ | `tests/test_validation.py` |
| A.8.27 | Secure system architecture | API / worker split, async ingest/search | ✅ | `tasks/dispatch.py` |
| A.8.28 | Secure coding | Tenant checks on all mutations | ✅ | Code review evidence |
| A.8.29 | Security testing in development | Unit tests | 🟡 | 📋 Integration tests, DAST |
| A.8.30 | Outsourced development | N/A if internal | — | |
| A.8.31 | Separation of environments | `PRISMRAG_ENV=development/production` | 🟡 | 📋 Staging/prod isolation |
| A.8.32 | Change management | Git, schema migrations | 🟡 | 📋 Change approval records |
| A.8.33 | Test information | Test fixtures, sample mappings | 🟡 | 📋 No prod data in tests policy |
| A.8.34 | Protection during audit testing | Audit log read access restricted | 🟡 | 📋 DB role separation |

---

## PrismRAG-specific evidence pack (quick reference)

| Auditor question | Where to look |
|------------------|---------------|
| Who can access customer data? | `tenant_member` + `assert_permission()` |
| How are API calls logged? | `prismrag.api_request_log` |
| How are searches/ingests audited? | `search_result_log`, `ingest_result_log` |
| How is access authenticated? | JWT, `prk_` keys, OIDC (`auth/oidc.py`) |
| How are quotas enforced? | `metering/quota.py`, `usage_event` |
| How is data deleted? | `DELETE /api/v1/tenants/{id}` |
| How is data exported? | `GET /api/v1/tenants/{id}/export` |
| Secrets in production? | `JWT_SECRET` required when `PRISMRAG_ENV=production` |
| Non-blocking processing? | `job_queue`, `search_task`, `job_worker` |
| Monitoring? | `GET /metrics`, `X-Request-Id` |

---

## Certification roadmap (practical)

1. **Define ISMS scope** — e.g. “PrismRAG multi-tenant SaaS hosted on Azure, excluding customer on-prem MCP agents.”
2. **Statement of Applicability (SoA)** — Use this table; justify excluded controls.
3. **Risk assessment** — Top risks: tenant crossover, API key leak, Gemini data processing, Stripe PCI scope.
4. **Implement gaps** — Prioritize ❌ items: ISMS policy, MFA, incident response, backups/DR tests, vendor DPAs.
5. **Internal audit** — Collect 📋 evidence for 3+ months (logs, access reviews, change tickets).
6. **Stage 1** — Documentation review with accredited registrar (BSI, SGS, etc.).
7. **Stage 2** — On-site/remote audit of controls in operation.
8. **Surveillance** — Annual audits to maintain certificate.

**Typical timeline:** 12–18 months first certification. **Cost:** $30k–$150k+ depending on scope and consultant.

**Alternative:** SOC 2 Type II (US-focused) overlaps ~70% with ISO 27001; platforms like Vanta/Drata accelerate evidence collection.

---

## Priority gap list (product + org)

| Priority | Gap | Action |
|----------|-----|--------|
| P0 | ISMS policy & risk register | Consultant or template + management sign-off |
| P0 | MFA for dashboard/login | Add TOTP or IdP-enforced MFA via OIDC |
| P0 | Backup & restore tested | Postgres PITR + quarterly restore drill |
| P1 | Incident response runbook | Document + tabletop exercise |
| P1 | Vendor DPAs | Google (Gemini), Stripe, Azure |
| P1 | Alerting on `/metrics` | Error rate, queue depth, failed jobs |
| P2 | Penetration test | Annual third-party test |
| P2 | SCIM / automated access reviews | Enterprise HR integration |

---

*Last updated: June 2026 — aligned with PrismRAG v1.0 enterprise features.*
