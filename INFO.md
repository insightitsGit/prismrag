# PrismRAG — Product Information (Landing Page Source)

> **Use this file** as the canonical source for website copy, sales one-pagers, and README summaries.  
> **Product:** Free Apache-2.0 Python library on PyPI — [`prismrag-patch` **0.2.1**](https://pypi.org/project/prismrag-patch/0.2.1/) (**published**, no license key).  
> **Legacy:** Azure SaaS API retired. Code in `prismrag/` for self-host reference only.  
> **Last benchmark:** 2026-06-24 — [examples/demo_app](examples/demo_app) vs PyPI install (see below).

---

## One-line pitch

**PrismRAG stops RAG category bleed** — you define your mapping (categories + word→category rules); the library ingests, builds a graph on *your* taxonomy, and runs Graph RAG search with a full audit trail. **`pip install prismrag-patch`**. Free. No hosted API required.

---

## Elevator pitch (30 seconds)

Standard Graph RAG learns relationships from document co-occurrence — two companies with the same PDFs get the same graph. **PrismRAG inverts that:** you supply a **mapping table** (categories + rules), and every chunk is embedded into *your* personal vector space. Retrieval uses Graph RAG (communities → word graph → re-rank) on a graph **you own**.

Ship with **`pip install prismrag-patch`**. Prototype in-memory, run production on **Postgres** (`PostgresStore` + `prismrag.*` tables), or add Tier-1 remap to **pgvector / Chroma / Pinecone / Weaviate**. Your data stays in your environment.

---

## Your mapping drives everything

Users define taxonomy once; the library executes on it:

```python
mapping = {
    "categories": [
        {"slug": "medication",  "label": "Medication"},
        {"slug": "lab_results", "label": "Lab Results"},
    ],
    "rules": [
        {"word": "metformin", "category_slug": "medication"},
        {"word": "troponin",  "category_slug": "lab_results"},
    ],
}
rag = PrismRAG(mapping=mapping, tenant_id="your-tenant")
```

| Source | How |
|--------|-----|
| Python dict / JSON file | Pass `mapping=` to `PrismRAG` or `PrismRAGPatch` |
| CSV / Excel / your SQL table | Load rows → build `categories` + `rules` → pass `mapping=` |
| Postgres production | `prismrag.mapping_category` + `prismrag.mapping_rule` via `PostgresStore` |
| Live updates | `append_chunks(..., new_rules=[...])` without full retrain |

Every ingest, projection, graph edge, and search result traces back to **your** rules — not Wikipedia co-occurrence.

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
11. **Reference demo + benchmarks** — `examples/demo_app` installs from PyPI, logs every event, 13 integration tests  

---

## Verified benchmark (PyPI 0.2.1)

Reproducible reference run: **`examples/demo_app/run_verification.py`**  
Install source: **PyPI** (`prismrag-patch==0.2.1`), not editable local code.  
Environment: Python 3.12.10, Windows, `MemoryStore`, deterministic embeddings (offline).

### Run summary

| Metric | Result |
|--------|--------|
| **Overall** | PASS (exit 0) |
| **Demo pipeline** | 0.29 s |
| **Integration tests** | **13 / 13 passed** in 0.29 s |
| **Total verification** | ~0.8 s |
| **Package** | `prismrag-patch` 0.2.1 from PyPI |

### Demo workload (healthcare mini-mapping)

| Setting | Value |
|---------|-------|
| Categories | 3 (`medication`, `lab_results`, `symptoms`) |
| Mapping rules | 6 words |
| Store | In-memory |
| Tier-1 alpha | 0.35 |

### Pipeline events (from event log)

| Step | Metric | Value |
|------|--------|-------|
| **Ingest** | Records written | 6 |
| | Communities (Louvain) | 3 |
| | Graph edges | 3 |
| | Job status | `completed` |
| **Search** | Query | *"What medications are used for diabetes management?"* |
| | Retrieval mode | `graph_rag` |
| | Hits (top_k=3) | 3 |
| | Top categories | `lab_results` (hba1c), `medication` (metformin, insulin) |
| **Communities** | Clusters | meds · labs · symptoms (2 words each) |
| **Bridge** | Created | bridge_id 1 (medication ↔ lab_results) |
| **Append** | New chunk | `nausea` → symptoms, quality **1.0** |
| **Quality** | Total chunks | 7 (6 ingest + 1 append) |
| | Avg quality | **0.73** |
| | Flagged | **0** |
| | Avg confidence | 0.79 |
| **Export** | Chunks exported | 7 (256-d personal + 768-d semantic each) |

### Integration test coverage (13 tests)

| Area | Tests | Status |
|------|-------|--------|
| Package import, no license key | 2 | PASS |
| Ingest, dual vectors, communities | 3 | PASS |
| Graph RAG search, category filter, top_k, latency &lt; 3 s | 5 | PASS |
| Append + quality report | 2 | PASS |
| Bridge creation | 1 | PASS |

### Reproduce

```powershell
cd examples/demo_app
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
python run_verification.py
```

Event log written to `examples/demo_app/logs/run_<timestamp>.log` (structured `EVENT name | {json}` per step).

Reference log from benchmark run: `examples/demo_app/logs/run_20260624_174725.log`

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

**Can I use my own mapping table?**  
Yes. Load your categories and word→category rows into the `mapping` dict (or Postgres `mapping_category` / `mapping_rule` tables). The library does not invent categories — it executes on what you define.

**Is the package verified on PyPI?**  
Yes. See **Verified benchmark** above — 13/13 integration tests against `prismrag-patch==0.2.1` installed from PyPI.

---

## Links

| Resource | URL |
|----------|-----|
| PyPI (0.2.1) | https://pypi.org/project/prismrag-patch/0.2.1/ |
| GitHub | https://github.com/insightitsGit/prismrag |
| Demo app + benchmark | [examples/demo_app](examples/demo_app) |
| Library docs page | https://prismrag.insightits.com/prismrag-lib.html |
| Whitepaper | https://prismrag.insightits.com/whitepaper.html |
| Package README | [prismrag_patch/README.md](prismrag_patch/README.md) |
| Technical deep-dive | [DOC/technical.md](DOC/technical.md) |
| Publish guide | [DOC/pypi-publish.md](DOC/pypi-publish.md) |

---

## Repo layout

| Path | Role |
|------|------|
| `prismrag_patch/` | **Ship this** — PyPI package (0.2.1 live) |
| `examples/demo_app/` | **Benchmark** — PyPI install, demo, 13 tests, event logs |
| `prismrag/` | Legacy SaaS API — reference / self-host |
| `web/` | Static marketing site |
| `tests/test_lib_*.py` | Library parity + evaluation tests (CI) |
| `prismrag/schema.sql` | Postgres schema for PostgresStore |

---

## Version

| Item | Value |
|------|-------|
| **PyPI release** | **0.2.1** — published (local `twine`, 2026-06-17) |
| **Source of truth** | `prismrag_patch/pyproject.toml` |
| **Next release** | Bump version → build → `twine upload` (only when library code changes) |

© 2026 Insight IT Solutions · Apache-2.0
