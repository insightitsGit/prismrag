# PrismRAG — Agent Handoff & Project Status

> Last updated: 2026-06-17  
> Branch: `main`  
> GitHub: https://github.com/aminparva84/InsightPrismRAG  
> **Product:** pip-only OSS library `prismrag-patch` v0.2.1

---

## Current status

| Component | Status | Detail |
|-----------|--------|--------|
| **PyPI package** | ✅ **Published** | [prismrag-patch 0.2.1](https://pypi.org/project/prismrag-patch/0.2.1/) — published via local `twine` |
| **Library CI** | ✅ | `.github/workflows/ci.yml` — tests + wheel build |
| **PyPI publish workflow** | ⏭️ Optional | `PYPI_API_TOKEN` for CI; v0.2.1 already on PyPI (skip re-tag or bump version) |
| **Azure SaaS** | ❌ Retired | `prismrag-rg` deleted — zero hosting cost |
| **Legacy API code** | 📦 Archived | `prismrag/` kept in repo for self-host reference |
| **Marketing site** | 📄 Static | `web/` — pip-first copy (see INFO.md) |
| **PostgresStore** | ✅ | Library writes `prismrag.*` schema directly |

---

## What to ship

**Primary deliverable:** `prismrag_patch/` on PyPI.

```bash
pip install "prismrag-patch[graph]"
from prismrag_patch import PrismRAG
```

**Canonical product doc:** [INFO.md](../INFO.md) — landing page source.

---

## Key paths

| Path | Purpose |
|------|---------|
| `INFO.md` | Landing page / sales copy source |
| `prismrag_patch/` | PyPI package |
| `prismrag_patch/README.md` | Package docs |
| `tests/test_lib_step*.py` | Step-by-step parity tests |
| `prismrag/schema.sql` | Postgres schema for PostgresStore |
| `prismrag/` | Legacy SaaS (FastAPI, worker, billing) |
| `DOC/pypi-publish.md` | How to publish |
| `DOC/azure-teardown.md` | Azure removal notes |

---

## Publish checklist

1. ~~Publish `0.2.1` to PyPI~~ — **done** (2026-06-17, local `twine upload`)
2. Verify: `pip install "prismrag-patch[graph]==0.2.1"`
3. Next release: bump `prismrag_patch/pyproject.toml`, rebuild, `twine upload`, tag `v0.2.2`

---

## Legacy SaaS (do not redeploy without intent)

- Azure deploy workflow archived: `.github/workflows/deploy.yml.archived`
- GitHub secrets (ACR, AZURE_CREDENTIALS, etc.) can be removed from repo settings
- Shared Postgres `psql-insight-hospital-prod` was **not** in `prismrag-rg` — still exists separately

---

## Contact

prismrag@insightits.com · Insight IT Solutions
