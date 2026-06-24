# PrismRAG — Deployment Guide

> **Primary deployment (2026):** `pip install prismrag-patch` — no Azure required.  
> See [INFO.md](../INFO.md) and [pypi-publish.md](pypi-publish.md).

---

## Option 1: Local / notebook (fastest)

```bash
pip install "prismrag-patch[graph]"
```

```python
from prismrag_patch import PrismRAG

rag = PrismRAG(mapping=your_mapping, tenant_id="dev")
rag.ingest(records=[...])
print(rag.search("your query", top_k=5))
```

Uses **MemoryStore** — nothing to deploy. Ideal for prototypes and CI tests.

---

## Option 2: Your PostgreSQL (production)

1. **Provision Postgres** with [pgvector](https://github.com/pgvector/pgvector) extension.
2. **Apply schema:**
   ```bash
   psql $DATABASE_URL -f prismrag/schema.sql
   ```
3. **Install library:**
   ```bash
   pip install "prismrag-patch[graph,pgvector]"
   ```
4. **Run client:**
   ```python
   from prismrag_patch import PrismRAG

   rag = PrismRAG.from_postgres(
       dsn=os.environ["PRISMRAG_DB_DSN"],
       mapping=mapping,
       tenant_id=tenant_uuid,
   )
   rag.ingest(records=[...])
   ```

PostgresStore writes to the same `prismrag.*` tables the former SaaS API used.

---

## Option 3: Existing vector database (remap only)

If you already have chunks in pgvector, Chroma, Pinecone, or Weaviate:

```bash
pip install "prismrag-patch[pgvector]"   # or chroma / pinecone / weaviate
```

```python
from prismrag_patch import PrismRAGPatch
from prismrag_patch.adapters.pgvector import PgvectorAdapter

patch = PrismRAGPatch(mapping=mapping)  # no license key
adapter = PgvectorAdapter(patch, conn, table="my_chunks")
adapter.insert(text, your_embed_fn(text))
results = adapter.search(query_text, query_vector, top_k=5)
```

This applies **Tier-1 category projection** on insert/search. For full Graph RAG (communities, bridges), use Option 1 or 2.

---

## Option 4: Self-host legacy SaaS API (advanced)

The FastAPI app in `prismrag/` + Dockerfiles can still be self-hosted if you need REST, auth, billing, and MCP. This path is **not maintained as the primary product** and Azure templates are archived.

Historical reference: [deploy.yml.archived](../.github/workflows/deploy.yml.archived), `infra/deploy.sh`.

---

## CI / PyPI publish

- **Tests:** `.github/workflows/ci.yml`
- **Publish:** tag `v*` → `.github/workflows/publish-pypi.yml` (requires `PYPI_API_TOKEN` secret)

```bash
git tag v0.2.1 && git push origin v0.2.1
```

---

## Azure SaaS (retired)

Hosted API at `prismrag.insightits.com` was shut down. Resource group `prismrag-rg` deleted — see [azure-teardown.md](azure-teardown.md).

---

## Environment variables (library)

| Variable | Used when |
|----------|-----------|
| `PRISMRAG_DB_DSN` | PostgresStore / integration tests |
| `GEMINI_API_KEY` | Optional; only if you wire Gemini embed_fn in app code |

The library does **not** require cloud secrets for core operation.

---

## Health checks

Library smoke test:

```bash
pytest tests/test_lib_step01_mapping.py tests/test_lib_step02_ingest.py -q
```

Postgres integration (optional):

```bash
PRISMRAG_DB_DSN=postgresql://... python scripts/run_postgres_lib_tests.py
```
