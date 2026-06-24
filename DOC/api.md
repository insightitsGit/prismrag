# PrismRAG — API Reference

> **Primary API (2026):** Python library `prismrag_patch` — see [INFO.md](../INFO.md).  
> Legacy REST API below is **archived** (SaaS retired); code remains in `prismrag/api/`.

---

## Library API (`prismrag-patch`)

### Install

```bash
pip install "prismrag-patch[graph]"
```

### Client

```python
from prismrag_patch import PrismRAG, PostgresStore, PrismRAGPatch
```

### PrismRAG methods

| Method | Description |
|--------|-------------|
| `PrismRAG(mapping=, tenant_id=, store=, embed_fn=)` | Create client (MemoryStore default) |
| `PrismRAG.from_postgres(dsn, mapping, tenant_id)` | Postgres-backed client |
| `ingest(records=, inline_config=, strategy="rules")` | Full ingest pipeline |
| `get_job(job_id)` | Job status dict |
| `search(query, top_k=5, category_filter=None)` | Graph RAG search |
| `list_communities()` | Community summaries |
| `create_bridge(community_a, community_b, bridge_label=)` | Bridge vector |
| `append_chunks(chunks, new_rules=, ml_fallback="auto")` | Incremental ingest |
| `chunk_quality()` | Quality scores + summary |
| `export_chunks()` | All chunks with dual vectors |

### Example

```python
rag = PrismRAG(mapping={"categories": [...], "rules": [...]}, tenant_id="demo")
job = rag.ingest(records=[{"word": "diabetes", "text": "diabetes care"}])
results = rag.search("insulin medication", top_k=5, category_filter="medication")
```

### PostgresStore

```python
store = PostgresStore(dsn="postgresql://...")
store.ensure_tenant(tenant_id)
store.ensure_schema()  # verifies prismrag.* tables exist
```

### PrismRAGPatch + adapters (Tier-1 remap only)

```python
patch = PrismRAGPatch(mapping=mapping)
patch.remap_vector(vector, text="volatility risk report")
patch.category_for("volatility in markets")
```

Adapters: `PgvectorAdapter`, `ChromaAdapter`, `PineconeAdapter`, `WeaviateAdapter`.

---

## Legacy REST API (archived SaaS)

Base path was `/api/v1/prismrag`. Requires JWT/API key, Azure deployment (retired).

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/jobs` | POST | Submit ingest job |
| `/jobs/{id}` | GET | Job status |
| `/search` | POST | Graph RAG search |
| `/communities` | GET | List communities |
| `/bridge` | POST | Create bridge |
| `/tenants/{id}/chunks/append` | POST | Append chunks |
| `/tenants/{id}/chunks/quality` | GET | Quality report |

Library method parity: [prismrag_patch/README.md](../prismrag_patch/README.md#api-parity-matrix).

---

## Embedding

Bring your own `embed_fn`:

```python
def my_embed(texts: list[str]) -> list[list[float] | None]:
    ...

rag = PrismRAG(mapping=mapping, embed_fn=my_embed)
```

Offline tests use deterministic hash embeddings (no API key).

---

## Further reading

- [INFO.md](../INFO.md)
- [technical.md](technical.md)
- [architecture.md](architecture.md)
