# PrismRAG — Product Information (Landing Page Source)

> **Use this file** as the canonical source for website copy, sales one-pagers, and README summaries.  
> **Product form:** Free Apache-2.0 Python library on PyPI (`prismrag-patch`).  
> **Legacy:** SaaS API on Azure was retired (zero hosting cost). Code remains in `prismrag/` for reference and self-host.

---

## One-line pitch

**PrismRAG stops RAG category bleed** by enforcing *your* taxonomy in vector space — deterministic category projection, graph RAG on your rules, fully auditable, pip-installable, no license key.

---

## Elevator pitch (30 seconds)

Standard Graph RAG learns relationships from document co-occurrence — so two companies with the same PDFs get the same graph. PrismRAG reverses that: **you define categories and word→category rules first**, then every chunk is embedded into *your* personal vector space. Retrieval runs Graph RAG (communities → word graph → semantic re-rank) on a graph **you own**, not Wikipedia’s statistics.

Ship it with **`pip install prismrag-patch`**. Run in-memory for prototypes, against **your Postgres** (`PostgresStore`), or drop Tier-1 remap into **pgvector / Chroma / Pinecone / Weaviate** via adapters. No SaaS subscription. No data leaves your environment unless you choose.

---

## What it does

| Capability | Description |
|------------|-------------|
| **Tier-1 rules mapping** | Auditable word→category assignment; 768-d semantic → 256-d personal projection |
| **Ingest pipeline** | Inline records → dual vectors → word graph → Louvain communities |
| **Graph RAG search** | Community routing → BFS on word graph → semantic re-rank (with direct fallback) |
| **Bridge vectors** | Synthetic connectors between communities for cross-topic retrieval |
| **Append mode** | Add chunks + rules without full retrain; quality scoring per chunk |
| **Vector DB adapters** | Remap + category metadata on insert/search (pgvector, Chroma, Pinecone, Weaviate) |
| **Postgres store** | Same `prismrag.*` schema as former SaaS — library talks to DB directly |

---

## Who it’s for

- **Engineering teams** building RAG on their own Postgres or vector DB who need taxonomy enforcement, not statistical graph guessing.
- **Regulated domains** (healthcare, finance, legal) where every retrieval must trace to an explicit rule.
- **Consultancies** white-labeling domain-specific knowledge graphs per client with isolated mappings.
- **Researchers** reproducing Graph RAG + category projection without a hosted API.

---

## How it’s different

| Standard Graph RAG | PrismRAG |
|--------------------|----------|
| Graph from co-occurrence / LLM extraction | Graph from **your mapping rules** + semantic edges |
| Same docs → same graph for everyone | Same docs → **different graphs** per client taxonomy |
| Black-box category assignment | Every chunk traces to **`mapping_rule`** row |
| Hosted platform lock-in | **`pip install`**, run locally or on your cloud |
| Pay per API call / seat | **Free** (Apache-2.0) |

---

## Architecture (pip library)

```
Your Python app
    │
    ▼
PrismRAG client  (from prismrag_patch import PrismRAG)
    │
    ├─ ingest(records)     → mapping + chunks + graph + communities
    ├─ search(query)       → graph RAG or direct semantic fallback
    ├─ list_communities()  → Louvain clusters + labels
    ├─ create_bridge(a,b)  → cross-community connector
    └─ append_chunks(...)  → incremental updates + quality scores
    │
    ▼
Store backend (choose one)
    ├─ MemoryStore      — zero setup, tests, notebooks
    ├─ PostgresStore    — production, prismrag.* tables + pgvector
    └─ Vector adapters  — remap only, your existing chunk table
```

**Dual vectors per chunk**

- **768-d semantic** — your embedding model (Gemini, OpenAI, local); used for community centroids and re-ranking.
- **256-d personal** — category-grounded projection; separates categories in retrieval space.

---

## Install

```bash
pip install prismrag-patch                      # core
pip install "prismrag-patch[graph]"             # + Louvain communities (recommended)
pip install "prismrag-patch[graph,pgvector]"    # + PostgresStore + pgvector adapters
pip install "prismrag-patch[all]"               # all optional deps
```

**Requirements:** Python 3.9+. No license key. No network calls for core operation.

---

## Quick start (copy for landing hero)

```python
from prismrag_patch import PrismRAG

mapping = {
    "categories": [
        {"slug": "risk",   "label": "Risk & Compliance"},
        {"slug": "growth", "label": "Growth & Revenue"},
    ],
    "rules": [
        {"word": "volatility", "category_slug": "risk"},
        {"word": "revenue",    "category_slug": "growth"},
    ],
}

rag = PrismRAG(mapping=mapping, tenant_id="demo")
rag.ingest(records=[
    {"word": "volatility", "text": "Market volatility increased"},
    {"word": "revenue",    "text": "Q3 revenue beat estimates"},
])

hits = rag.search("What are the risk metrics?", top_k=5)
for h in hits["results"]:
    print(h["category_slug"], h["score"], h["chunk_text"][:60])
```

---

## Postgres production path

```python
from prismrag_patch import PrismRAG

rag = PrismRAG.from_postgres(
    dsn="postgresql://user:pass@host:5432/prismrag",
    mapping=mapping,
    tenant_id="your-tenant-uuid",
)
rag.ingest(records=[...])
print(rag.search("credit risk VaR", top_k=10))
```

Apply schema once: `prismrag/schema.sql` (pgvector extension required).

---

## Feature list (for landing bullets)

1. **Deterministic Tier-1 projection** — reproducible 768→256 mapping; same rules → same vectors  
2. **Graph RAG retrieval** — community seeding, BFS expansion, semantic re-rank  
3. **Louvain communities** — automatic topic clusters with optional LLM labels  
4. **Bridge vectors** — link two communities for cross-domain queries  
5. **Chunk quality scoring** — confidence, separation, coherence; flag low-quality assignments  
6. **Append without retrain** — upsert new chunks; merge new rules  
7. **Category filter on search** — restrict results to one taxonomy branch  
8. **Tenant + mapping isolation** — multi-workspace via `tenant_id` + `mapping_id`  
9. **Vector DB adapters** — pgvector, ChromaDB, Pinecone, Weaviate  
10. **Step-by-step test suite** — `tests/test_lib_step*.py` parity harness  

---

## API surface (library)

| Method | Purpose |
|--------|---------|
| `PrismRAG(mapping=..., tenant_id=...)` | Create client (MemoryStore default) |
| `PrismRAG.from_postgres(dsn, ...)` | Production Postgres backend |
| `rag.ingest(records=[...])` | Full pipeline: map → embed → graph → communities |
| `rag.search(query, top_k=, category_filter=)` | Graph RAG search |
| `rag.list_communities()` | Cluster summaries + top words |
| `rag.create_bridge(a, b, bridge_label=)` | Bridge vector between communities |
| `rag.append_chunks(chunks, new_rules=)` | Incremental ingest |
| `rag.chunk_quality()` | Quality report for all chunks |
| `rag.export_chunks()` | Export dual vectors + metadata |

Legacy SaaS REST paths are documented in `DOC/api.md` (archived; code in `prismrag/`).

---

## Use cases (landing “Built for” section)

### Healthcare
Map clinical concepts (`diagnosis`, `medication`, `lab_results`, `patient_safety`). Search “insulin management” returns medication-category chunks, not random co-occurring symptoms.

### Finance
Categories: `risk`, `valuation`, `liquidity`, `regulatory`. Enforce that “VaR” and “volatility” stay in `risk` even when embeddings would blur lines with `growth`.

### Pharmacy / Life sciences
Drug interactions, pharmacokinetics, storage — separate slugs prevent cross-contamination in agent retrieval.

### Enterprise knowledge bases
Each business unit submits a mapping JSON; same SharePoint export yields different graphs per unit.

---

## FAQ (landing / schema.org)

**Is PrismRAG free?**  
Yes. `prismrag-patch` is Apache-2.0 on PyPI. No license key, no usage metering in the library.

**Do I need Gemini or OpenAI?**  
You bring your own embedding function. The library includes deterministic embeddings for offline tests. Production typically uses Gemini, OpenAI, or local models.

**Does data leave my environment?**  
No, when using the pip library locally or with your Postgres. Optional community labeling can call an LLM if you configure it.

**What happened to the hosted API?**  
The Azure SaaS deployment was retired to eliminate cost. The same algorithms live in the library; `prismrag/` source remains for self-hosters.

**How is this different from LangChain / LlamaIndex?**  
PrismRAG is a **taxonomy-grounded retrieval engine**, not a general orchestration framework. Use it inside or beside those tools for category-safe Graph RAG.

**Can I use only the vector remap (Tier-1 patch)?**  
Yes. `PrismRAGPatch` + adapters remap vectors on insert/search without full graph pipeline.

---

## Links

| Resource | URL |
|----------|-----|
| PyPI | https://pypi.org/project/prismrag-patch/ |
| GitHub | https://github.com/aminparva84/InsightPrismRAG |
| Library docs page | https://prismrag.insightits.com/prismrag-lib.html |
| Whitepaper | https://prismrag.insightits.com/whitepaper.html |
| Package README | [prismrag_patch/README.md](prismrag_patch/README.md) |
| Technical deep-dive | [DOC/technical.md](DOC/technical.md) |
| Publish guide | [DOC/pypi-publish.md](DOC/pypi-publish.md) |

---

## Repo layout

| Path | Role |
|------|------|
| `prismrag_patch/` | **Ship this** — PyPI package |
| `prismrag/` | Legacy SaaS API (FastAPI, worker, billing) — reference / self-host |
| `web/` | Static marketing site |
| `tests/test_lib_*.py` | Library parity + evaluation tests |
| `prismrag/schema.sql` | Postgres schema for PostgresStore |

---

## Version

Current library version: **0.2.1** (see `prismrag_patch/pyproject.toml`).

---

© 2026 Insight IT Solutions · Apache-2.0
