# PrismRAG

**Taxonomy-grounded retrieval for production AI**

PyPI package: [`prismrag-patch`](https://pypi.org/project/prismrag-patch/) (Apache-2.0)

```bash
pip install "prismrag-patch[graph]"
```

[![PyPI](https://img.shields.io/pypi/v/prismrag-patch)](https://pypi.org/project/prismrag-patch/0.2.1/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](prismrag_patch/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/prismrag-patch)](https://pypi.org/project/prismrag-patch/)

---

## What is this?

PrismRAG is a Python library that makes retrieval follow **your taxonomy** (categories + word→category rules).

You define the mapping. The library:

1. Assigns each chunk a category from your rules  
2. Builds dual vectors (semantic + category-grounded)  
3. Builds a word graph and communities from that mapping  
4. Searches with graph-aware retrieval (`graph_rag`) or direct semantic fallback  
5. Returns `category_slug` on every hit so results are auditable  

**Package name:** `prismrag-patch` · **Import:** `prismrag_patch` · **Version:** 0.2.1

---

## Who is it for?

- Engineers running RAG on Postgres or a vector DB who need **category boundaries**, not only cosine similarity  
- Teams in healthcare, finance, legal, or multi-tenant KB where retrieval must explain **which rule** applied  
- Teams evaluating GraphRAG who want relationship-aware retrieval **without** a separate graph database  

---

## What problem does it solve?

**Category bleed:** similarity search returns the wrong domain slice (e.g. growth text for a risk query, symptoms for a medication query).

**Opaque graphs:** traditional GraphRAG often builds edges from co-occurrence or LLM extraction. Same docs → same graph for every tenant. Hard to audit.

PrismRAG inverts that: **your mapping builds the graph**. Same docs + different mappings → different retrieval behavior per tenant.

---

## What does it replace / complement / integrate with?

| Relationship | Technology | Meaning |
|--------------|------------|---------|
| **Alternative to** | Co-occurrence / auto GraphRAG stacks | Relationship-aware retrieval from *your* rules, not corpus statistics |
| **Complements** | LangChain, LlamaIndex, custom RAG apps | Retrieval engine inside or beside your orchestrator — not a replacement for agent frameworks |
| **Not a replacement for** | LangGraph, AutoGen, CrewAI | Those orchestrate agents/workflows; PrismRAG retrieves context |
| **Integrates with** | pgvector, Chroma, Pinecone, Weaviate | Tier-1 remap adapters keep your existing chunk store |
| **Integrates with** | Postgres + pgvector | `PostgresStore` for full graph pipeline persistence |
| **Does not replace** | Your embedding model | Bring your own `embed_fn` |

Short positioning: **taxonomy-grounded retrieval layer** — alternative approach to traditional GraphRAG, complementary to LangChain/LlamaIndex, not an agent runtime.

---

## Quick start

```python
from prismrag_patch import PrismRAG

mapping = {
    "categories": [
        {"slug": "risk", "label": "Risk & Compliance"},
        {"slug": "growth", "label": "Growth & Revenue"},
    ],
    "rules": [
        {"word": "volatility", "category_slug": "risk"},
        {"word": "drawdown", "category_slug": "risk"},
        {"word": "revenue", "category_slug": "growth"},
    ],
}

rag = PrismRAG(mapping=mapping, tenant_id="demo")
rag.ingest(records=[
    {"word": "volatility", "text": "Market volatility spiked in Q3."},
    {"word": "drawdown", "text": "Drawdown exceeded the risk budget."},
    {"word": "revenue", "text": "Q3 revenue beat estimates."},
])

hits = rag.search("portfolio risk metrics", top_k=5)
for h in hits["results"]:
    print(h["category_slug"], h["chunk_ref"])
```

```bash
# Smoke demos
cd examples/graph-rag-replacement && pip install -r requirements.txt && python demo_taxonomy_connection.py
cd examples/demo_app && pip install -r requirements.txt && python run_verification.py
```

Live browser demo: https://insightitsgit.github.io/prismrag/demo.html

---

## When to use it

- You can define (or load) a **category + rules** mapping  
- You need **auditable** category placement on chunks  
- You want graph-style retrieval **without** Neo4j / entity-extraction GraphRAG  
- You already have (or want) pgvector / Chroma / Pinecone / Weaviate / Postgres  

## When NOT to use it

- You refuse any taxonomy and want a fully unsupervised corpus graph → classic auto GraphRAG fits better  
- You need an agent orchestration framework → use LangGraph / similar; call PrismRAG from tools  
- You only need plain vector search with no categories → a vector DB alone is enough  
- You expect built-in Supports/Contradicts edge types as first-class enums → today you encode roles via **categories and rules**, not typed edge labels  

---

## Architecture (where it fits)

```
Application / agents (LangChain, custom API, …)
        │
        ▼
┌───────────────────┐
│ Vector DB / PG    │  ← keep your store
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ PrismRAG          │  ← mapping · dual vectors · graph search
│ (this library)    │
└─────────┬─────────┘
          │
          ▼
   Explainable hits
   (category_slug, refs)
          │
          ▼
        LLM
```

Details: [docs/architecture.md](docs/architecture.md)

---

## Documentation

| Doc | Answers |
|-----|---------|
| **[docs/ai-overview.md](docs/ai-overview.md)** | Concise summary for humans and coding assistants |
| [docs/overview.md](docs/overview.md) | What / who / why |
| [docs/architecture.md](docs/architecture.md) | Stack placement and data flow |
| [docs/concepts.md](docs/concepts.md) | Mapping, dual vectors, graph, bridges, stores |
| [docs/migration.md](docs/migration.md) | Switch from vector-only or GraphRAG |
| [docs/examples.md](docs/examples.md) | Practical patterns |
| [docs/comparison.md](docs/comparison.md) | Factual comparisons |
| [docs/faq.md](docs/faq.md) | Common questions |
| [INFO.md](INFO.md) | Product canon + benchmarks |
| [prismrag_patch/README.md](prismrag_patch/README.md) | Package API |

---

## Main APIs

| Symbol | Purpose |
|--------|---------|
| `PrismRAG` | Full client: ingest, search, communities, bridges, append, quality, export |
| `PrismRAG.from_postgres(dsn, …)` | Same client on `PostgresStore` |
| `PrismRAGPatch` | Tier-1 remap only (adapters) |
| `MemoryStore` / `PostgresStore` | Persistence backends |
| Adapters | `PgvectorAdapter`, `ChromaAdapter`, `PineconeAdapter`, `WeaviateAdapter` |

See [docs/concepts.md](docs/concepts.md) for why each exists and common mistakes.

---

## Install

```bash
pip install prismrag-patch                      # core
pip install "prismrag-patch[graph]"             # + Louvain communities (recommended)
pip install "prismrag-patch[graph,pgvector]"    # + Postgres / pgvector
pip install "prismrag-patch[all]"
```

Python ≥ 3.9. No license key. Core path needs no network.

---

## Philosophy

PrismRAG intentionally:

- Puts **your mapping** before corpus statistics  
- Keeps **chunks separate** (no mega-chunk merge)  
- Stays a **library**, not a hosted SaaS requirement  
- Does **not** replace vector DBs, embedding models, or agent frameworks  

---

## License

Apache-2.0 — [prismrag_patch/LICENSE](prismrag_patch/LICENSE)

Maintained by [Insight IT Solutions](https://www.insightits.com) · GitHub [insightitsGit/prismrag](https://github.com/insightitsGit/prismrag)
