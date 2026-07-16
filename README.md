# PrismRAG

**Semantic Retrieval Architecture for Production AI**

Explainable, taxonomy-grounded retrieval for production AI — stop category bleed, control how knowledge connects, and optionally replace heavy GraphRAG pipelines while staying on your existing vector database.

- **Your taxonomy drives retrieval** — categories + word→category rules you own
- **Works with existing vector stores** — pgvector, Chroma, Pinecone, Weaviate, or Postgres
- **No separate graph database required** — relationship-aware search without Neo4j
- **Explainable by design** — every hit traces to a mapping rule

```bash
pip install "prismrag-patch[graph]"
```

[![PyPI](https://img.shields.io/pypi/v/prismrag-patch)](https://pypi.org/project/prismrag-patch/0.2.1/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](prismrag_patch/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/prismrag-patch)](https://pypi.org/project/prismrag-patch/)

**Maintained by** [Insight IT Solutions](https://www.insightits.com) · **Live demo** [demo.html](https://insightitsgit.github.io/prismrag/demo.html) · **Package** [`prismrag-patch`](https://pypi.org/project/prismrag-patch/0.2.1/)

---

## The Problem

Traditional RAG treats documents as independent vectors. Similarity finds “nearby” text — not the evidence your domain actually needs. That produces **category bleed**: the wrong department, clause type, or clinical concept ranks high because embeddings blurred the boundary.

Traditional GraphRAG improves retrieval by adding relationships, but often forces a second architecture:

- Complex graph indexing and entity extraction
- A dedicated graph database beside your vector store
- Expensive preprocessing before anything is searchable
- Harder deployment and more moving parts
- Ongoing operational overhead for teams that already ship RAG

You should not have to redesign production architecture just to get taxonomy-safe, relationship-aware retrieval.

---

## The Solution

PrismRAG is a **taxonomy-first semantic layer** over the knowledge base you already have.

**Core idea:** you define a mapping (categories + word→category rules). PrismRAG projects every chunk into that space, builds an auditable word graph from your rules, and retrieves with category-aware GraphRAG-style search — or direct semantic fallback when needed.

It does not replace your vector database. It enhances it.

With that mapping you encode how knowledge relates in *your* domain — for example:

| Role | What you encode in taxonomy |
|------|-----------------------------|
| **Supports** | Evidence that backs a claim or procedure |
| **Contradicts** | Conflicting guidance that must surface together |
| **Depends On** | Prerequisites, dependencies, upstream facts |
| **Refines** | Narrower detail under a broader topic |
| **Temporal** | Before / after / versioned context |
| **Hierarchical** | Parent / child structure in your category tree |

**One outcome** of that design is replacing traditional GraphRAG pipelines. Taxonomy enforcement, dual vectors, append/quality, bridges, and vector-DB adapters are the product — GraphRAG replacement is a use case, not the only one.

---

## Your taxonomy is the product

Everything starts with a mapping you control:

```python
mapping = {
    "categories": [
        {"slug": "medication",  "label": "Medication"},
        {"slug": "lab_results", "label": "Lab Results"},
        {"slug": "symptoms",    "label": "Symptoms"},
    ],
    "rules": [
        {"word": "metformin", "category_slug": "medication"},
        {"word": "troponin",  "category_slug": "lab_results"},
        {"word": "fever",     "category_slug": "symptoms"},
    ],
}
```

| Source | How |
|--------|-----|
| Python dict / JSON | Pass `mapping=` to `PrismRAG` |
| CSV / Excel / your SQL table | Load rows → build categories + rules |
| Postgres production | `prismrag.mapping_category` + `prismrag.mapping_rule` |
| Live updates | `append_chunks(..., new_rules=[...])` without full retrain |

Same documents + different mappings = different retrieval graphs per tenant or business unit. That is the multi-tenant / regulated-domain story — independent of whether you came looking for “GraphRAG.”

---

## Example

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
    {"word": "volatility", "text": "Market volatility spiked in Q3 amid rate uncertainty."},
    {"word": "drawdown", "text": "Portfolio drawdown exceeded the 10 percent risk budget."},
    {"word": "revenue", "text": "Q3 revenue beat estimates on enterprise ARR growth."},
])

# Taxonomy-aware search (graph_rag when the word graph helps)
hits = rag.search("What are the risk metrics for the portfolio?", top_k=5)
for h in hits["results"]:
    print(h["category_slug"], h["chunk_ref"], h["chunk_text"][:60])

# Hard boundary when you need it
risk_only = rag.search("portfolio metrics", top_k=5, category_filter="risk")

# Communities, bridges, quality, export
comms = rag.list_communities()
if len(comms) >= 2:
    rag.create_bridge(comms[0]["community_id"], comms[1]["community_id"])
print(rag.chunk_quality()["summary"])
chunks = rag.export_chunks()  # dual vectors + category metadata
```

Same-category terms get explicit **rule edges**. Chunks stay separate for citation. Search returns `category_slug` on every hit.

```bash
# Taxonomy connection smoke (~60s) — also proves GraphRAG replacement
cd examples/graph-rag-replacement
pip install -r requirements.txt
python demo_taxonomy_connection.py
```

Interactive walkthrough: https://insightitsgit.github.io/prismrag/demo.html

---

## What you get (full capability set)

| Capability | Benefit |
|------------|---------|
| **Client-defined taxonomy** | You own categories and rules; retrieval follows your domain model |
| **Tier-1 category projection** | Deterministic 768→256 personal vectors; stop category bleed |
| **Dual embeddings per chunk** | Semantic content + category-grounded space in one record |
| **Word graph + rule edges** | Same-category chunks connect without mega-chunk merge |
| **Louvain communities** | Topic clusters for routing and labeling |
| **GraphRAG-style search** | Community seed → graph hop → semantic re-rank (`graph_rag`) |
| **Direct search fallback** | Still works when the graph path is empty |
| **Category filter** | Hard SQL/metadata isolation at query time |
| **Bridge vectors** | Controlled cross-community hops without a graph DB |
| **Append + quality scoring** | Add chunks/rules incrementally; flag weak assignments |
| **Chunk export** | Take dual vectors + metadata into your own pipelines |
| **MemoryStore** | Zero-infra prototypes, notebooks, CI |
| **PostgresStore** | Production on `prismrag.*` schema |
| **Vector DB adapters** | Tier-1 remap on pgvector / Chroma / Pinecone / Weaviate |
| **BYO embeddings** | Pass `embed_fn` — OpenAI, Gemini, local, or deterministic tests |
| **Apache-2.0, no license key** | `pip install` — data stays in your environment |

---

## Use cases

### 1. Taxonomy enforcement (primary)
Stop category bleed in regulated and multi-tenant RAG. Healthcare meds vs labs, finance risk vs growth, legal clause types — every retrieval can cite the rule that placed the chunk.

### 2. GraphRAG pipeline replacement
When you need relationship-aware retrieval without Neo4j, entity-extraction jobs, or a second GraphRAG product. PrismRAG builds the graph from **your mapping**, not document co-occurrence.

### 3. Multi-tenant / white-label knowledge
Same corpus, different mapping JSON per client or business unit → isolated personal vector spaces and graphs.

### 4. Agent-safe retrieval
Agents hallucinate when context is wrong-category. Return category-tagged chunks and optional `category_filter` so tools only see the slice you allow.

### 5. Incremental production KB
Append new vocabulary and chunks without full re-ingest; quality scores catch bad assignments before they ship.

### Real-world sketches

| Domain | Why taxonomy + PrismRAG beats similarity alone |
|--------|------------------------------------------------|
| **Customer support** | Product areas stay separated; procedures don’t mix with unrelated tickets that share wording |
| **Legal search** | Clause types stay in the right bucket; opposing obligations don’t blend |
| **Medical knowledge** | Meds, labs, symptoms remain separable and auditable |
| **Financial research** | VaR / volatility / drawdown retrieve together under risk |
| **Security docs** | Control families and dependencies follow your hierarchy |
| **Enterprise search** | Per-BU mappings; one SharePoint dump → many tenant graphs |

---

## Why PrismRAG instead of traditional GraphRAG?

*This comparison matters when GraphRAG is the alternative you’re evaluating. PrismRAG’s foundation is still taxonomy — GraphRAG replacement is one reason teams adopt it.*

| | Traditional GraphRAG | PrismRAG |
|--|----------------------|----------|
| **Architecture** | Vector DB + graph DB + extraction pipeline | Taxonomy semantic layer on your existing stack |
| **Setup** | Entity graphs, indexing jobs, schema work | Define a mapping; ingest; search |
| **Graph storage** | Dedicated graph database | In-process word graph / optional Postgres |
| **Deployment** | Multi-service, high ops cost | `pip install` — MemoryStore or your Postgres |
| **Explainability** | Often opaque co-occurrence / LLM edges | Every hit traces to a mapping rule you wrote |
| **Relationship model** | Auto-extracted, hard to audit | You define taxonomy roles and category links |
| **Integration** | New retrieval stack to operate | Drop-in client or adapters for existing DBs |
| **Production readiness** | Heavy preprocessing before value | Incremental append, quality scores, category filters |
| **Vector store compatibility** | Often forces migration | pgvector, Chroma, Pinecone, Weaviate adapters |

You do not need another GraphRAG implementation to get relationship-aware retrieval. You need a taxonomy you own — PrismRAG runs on that.

---

## Architecture

```
┌─────────────────┐
│  Application    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Vector Database │  ← keep what you already run
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PrismRAG        │  ← taxonomy · dual vectors · graph retrieve
│ Semantic Layer  │     communities · bridges · append · quality
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Explainable     │  ← category_slug · rule trail · optional filter
│ Retrieval       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM / Agents    │
└─────────────────┘
```

PrismRAG sits between your store and the model. It does not become a third database you have to staff.

---

## Install

```bash
pip install prismrag-patch                      # core
pip install "prismrag-patch[graph]"             # + communities (recommended)
pip install "prismrag-patch[graph,pgvector]"    # + Postgres + pgvector adapter
pip install "prismrag-patch[all]"               # all extras
```

Python 3.9+. No license key. Core path needs no network.

| Backend | When |
|---------|------|
| **MemoryStore** | Notebooks, tests, demos |
| **PostgresStore** | Production — [`prismrag/schema.sql`](prismrag/schema.sql) |
| **Vector adapters** | Remap on an existing chunk table |

Full API: [`prismrag_patch/README.md`](prismrag_patch/README.md)

---

## Philosophy

PrismRAG is not another vector database.

It is not another graph database.

It is not another embedding model.

It is a **semantic reasoning layer for retrieval** — taxonomy-grounded first, relationship-aware second, production-compatible with the vector stack you already run. Replacing a heavy GraphRAG pipeline is a powerful use case. Owning your taxonomy is the product.

---

## Ecosystem

PrismRAG is part of the [Prism AI](https://www.insightits.com) ecosystem from Insight IT Solutions:

| Project | Role |
|---------|------|
| **PrismRAG** | Taxonomy-grounded semantic retrieval (this repo) |
| **[PrismGuard](https://github.com/insightitsGit)** | Injection / safety controls for AI apps |
| **ChorusGraph / related Prism tools** | Agent and fabric tooling around production AI |

Use PrismRAG alone, or compose it with the rest of the stack as your architecture grows.

---

## Try it

| | |
|--|--|
| **Browser demo** | https://insightitsgit.github.io/prismrag/demo.html |
| **Taxonomy / GraphRAG smoke** | [`examples/graph-rag-replacement/`](examples/graph-rag-replacement/) |
| **PyPI verification** | [`examples/demo_app/`](examples/demo_app/) — 13/13 tests vs published `0.2.1` |
| **Product deep-dive** | [`INFO.md`](INFO.md) |
| **Scorecard** | [`docs/taxonomy-scorecard.md`](docs/taxonomy-scorecard.md) |

```bash
git clone https://github.com/insightitsGit/prismrag.git
cd prismrag/examples/graph-rag-replacement
pip install -r requirements.txt
python demo_taxonomy_connection.py
```

Soft CTA: reply **TAXONOMY** (issue / email `prismrag@insightits.com`) with a redacted mapping JSON for an async one-page connection map — no calendar required.

---

## Repo layout

| Path | Purpose |
|------|---------|
| [`prismrag_patch/`](prismrag_patch/) | PyPI package |
| [`examples/graph-rag-replacement/`](examples/graph-rag-replacement/) | Taxonomy connection + GraphRAG replacement smoke |
| [`examples/demo_app/`](examples/demo_app/) | Install verification + event logs |
| [`docs/demo.html`](docs/demo.html) | Interactive Pages demo |
| [`INFO.md`](INFO.md) | Product canon / FAQ / benchmarks |
| [`tests/test_lib_*.py`](tests/) | Library parity (CI) |
| [`prismrag/`](prismrag/) | Legacy SaaS reference (not required) |

---

## Development

```bash
pip install -e "prismrag_patch[graph]"
pytest tests/test_lib_step*.py -v

cd examples/graph-rag-replacement && python demo_taxonomy_connection.py
cd examples/demo_app && python run_verification.py
```

---

## License

Apache-2.0 — [`prismrag_patch/LICENSE`](prismrag_patch/LICENSE)

Published package: **`prismrag-patch` 0.2.1** on [PyPI](https://pypi.org/project/prismrag-patch/0.2.1/).
