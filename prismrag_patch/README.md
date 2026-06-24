# prismrag-patch

**Free OSS RAG library with full API core parity — ingest, graph RAG search, communities, bridges, append.**

Official site: **[prismrag.insightits.com](https://prismrag.insightits.com)** ·
PyPI: **[pypi.org/project/prismrag-patch](https://pypi.org/project/prismrag-patch/)**

## What's new in 0.2.0

- **No license key** — Apache-2.0, pip-only, fully offline
- **`PrismRAG` client** — mirrors SaaS core endpoints locally
- **Graph RAG** — word graph, Louvain communities, BFS retrieval
- **Dual vectors** — 768-d semantic + 256-d personal (RulesStrategy projection)
- **Append + quality scoring** — extend mappings without full retrain
- **Step-by-step tests** — `tests/test_lib_step*.py` + evaluation harness

## Quick start — full RAG pipeline (no DB required)

```python
from prismrag_patch import PrismRAG

mapping = {
    "categories": [
        {"slug": "medication", "label": "Medication"},
        {"slug": "lab_results", "label": "Lab Results"},
    ],
    "rules": [
        {"word": "metformin", "category_slug": "medication"},
        {"word": "troponin",  "category_slug": "lab_results"},
    ],
}

rag = PrismRAG(mapping=mapping, tenant_id="demo")
job = rag.ingest(records=[
    {"word": "metformin", "text": "metformin for diabetes"},
    {"word": "troponin",  "text": "troponin heart attack marker"},
])
print(job["status"], job["community_count"])

results = rag.search("What medications for diabetes?", top_k=5)
for hit in results["results"]:
    print(hit["category_slug"], hit["chunk_ref"])

comms = rag.list_communities()
bridge = rag.create_bridge(comms[0]["community_id"], comms[1]["community_id"])
quality = rag.chunk_quality()
```

## Vector DB adapters (Tier-1 remap)

Works with pgvector, ChromaDB, Pinecone, or Weaviate — bring your own embeddings:

```python
from prismrag_patch import PrismRAGPatch
from prismrag_patch.adapters.pgvector import PgvectorAdapter
import psycopg2

patch = PrismRAGPatch(mapping=mapping)  # no license_key
conn = psycopg2.connect("postgresql://user:pass@localhost/mydb")
adapter = PgvectorAdapter(patch, conn)
adapter.insert("metformin therapy", your_embed_fn("metformin therapy"))
```

## PostgreSQL store (SaaS schema parity)

Use the same ``prismrag.*`` tables as production — no HTTP API required:

```python
import os
from prismrag_patch import PrismRAG, PostgresStore

dsn = os.environ["PRISMRAG_DB_DSN"]  # postgresql://user:pass@host:5432/prismrag
tenant_id = "10000000-0000-0000-0000-000000000001"

# Option A: factory
rag = PrismRAG.from_postgres(dsn=dsn, mapping=mapping, tenant_id=tenant_id)

# Option B: explicit store
store = PostgresStore(dsn=dsn)
store.ensure_tenant(tenant_id)
rag = PrismRAG(mapping=mapping, tenant_id=tenant_id, store=store)

rag.ingest(records=[...])
print(rag.search("credit risk", top_k=5))
```

Requires ``prismrag/schema.sql`` applied to your database and ``pip install "prismrag-patch[graph,pgvector]"``.

Integration tests: ``PRISMRAG_DB_DSN=... pytest tests/test_lib_postgres_store.py -v``

## Installation

```bash
pip install prismrag-patch                      # core (mapping, ingest, search in-memory)
pip install "prismrag-patch[graph]"             # + networkx + python-louvain (communities)
pip install "prismrag-patch[pgvector]"          # + PostgreSQL adapter
pip install "prismrag-patch[all]"               # everything
```

## Running parity tests

```bash
cd prismrag_patch && pip install -e ".[graph]"
cd .. && pytest tests/test_lib_step01_mapping.py -v   # step 1: mapping
pytest tests/test_lib_step02_ingest.py -v              # step 2: ingest
pytest tests/test_lib_step03_graph.py -v               # step 3: graph/communities
pytest tests/test_lib_step04_search.py -v              # step 4: search
pytest tests/test_lib_step05_bridge_append.py -v     # step 5: bridge/append/quality
pytest tests/test_lib_step06_evaluation.py -v -s     # step 6: evaluation report
```

## API parity matrix

| SaaS endpoint | Library method |
|---------------|----------------|
| `POST /jobs` (inline ingest) | `rag.ingest(...)` |
| `GET /jobs/{id}` | `rag.get_job(job_id)` |
| `POST /search` | `rag.search(query, top_k=, category_filter=)` |
| `GET /communities` | `rag.list_communities()` |
| `POST /bridges` | `rag.create_bridge(a, b, bridge_label=)` |
| `POST /append` | `rag.append_chunks(...)` |
| `GET /chunks/quality` | `rag.chunk_quality()` |
| Chunk export | `rag.export_chunks()` |

## License

Apache-2.0 — free for commercial and personal use.

© 2026 Insight IT Solutions
