# PrismRAG

**You don’t need a separate Graph RAG stack.**

PrismRAG is taxonomy-grounded Graph RAG in one Apache-2.0 library: you define categories + word→category rules, same-category words get **rule edges**, dual embeddings power retrieval, and chunks stay separate — no mega-chunk, no co-occurrence guesswork.

```bash
pip install "prismrag-patch[graph]"
```

[![PyPI](https://img.shields.io/pypi/v/prismrag-patch)](https://pypi.org/project/prismrag-patch/0.2.1/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](prismrag_patch/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/prismrag-patch)](https://pypi.org/project/prismrag-patch/)

**Maintained by** [Insight IT Solutions](https://www.insightits.com) · **PyPI** [`prismrag-patch` 0.2.1](https://pypi.org/project/prismrag-patch/0.2.1/) · **Landing** https://www.insightits.com/products/prismrag.html

| Start here | Link |
|------------|------|
| **Live demo** (browser) | [`docs/demo.html`](docs/demo.html) → https://insightitsgit.github.io/prismrag/demo.html |
| **Smoke demo** (run Python) | [`examples/graph-rag-replacement/`](examples/graph-rag-replacement/) |
| **Taxonomy Scorecard** (read) | [`docs/taxonomy-scorecard.md`](docs/taxonomy-scorecard.md) |
| Product deep-dive | [`INFO.md`](INFO.md) |
| Package API | [`prismrag_patch/README.md`](prismrag_patch/README.md) |

---

## The real power (honest)

Standard Graph RAG builds a graph from **document co-occurrence** (or LLM extraction). Same PDFs → same graph for every tenant. When two base chunks should connect, you get a statistical guess — not a mapping you own.

**PrismRAG inverts that:**

1. **You customize the taxonomy** — categories + Tier-1 `word → category` rules  
2. **Same category → rule edge** — explicit graph link between base chunks (they stay separate)  
3. **Dual embeddings per chunk** — 768-d semantic + **256-d personal** (category-grounded projection)  
4. **Graph RAG search** — communities → word-graph hop → semantic re-rank (direct fallback when needed)  
5. **Optional bridges** — connect communities for cross-topic hops without merging documents  

So for domain RAG: **you do not bolt on another Graph RAG product.** PrismRAG already *is* the Graph RAG layer — taxonomy-first, auditable, pip-installable.

**Narrow caveat:** if you refuse any mapping and want a fully unsupervised corpus graph, classic auto GraphRAG is closer. Most regulated / multi-tenant RAG is not that case.

---

## Compete with (Dunford)

| We compete with | We do **not** compete with |
|-----------------|----------------------------|
| Co-occurrence / “auto” Graph RAG stacks | Vector DB vendors as the hero story |
| Vector-only lottery (similarity without taxonomy) | PrismGuard (injection firewall) · ChorusGraph (agent runtime) |
| Black-box “the model figured out the graph” | Hosted Graph RAG SaaS lock-in |

**Category one-liner:** taxonomy-grounded Graph RAG — your rules build the graph; co-occurrence Graph RAG guesses it from the corpus.

---

## Smoke it (60 seconds)

**Browser (PrismGuard-style interactive demo):**  
https://insightitsgit.github.io/prismrag/demo.html · source [`docs/demo.html`](docs/demo.html)

**CLI (real library):**
Proves shared category → rule edge → both chunks retrieved via `graph_rag` — and prints:

> You do NOT need a separate Graph RAG library beside PrismRAG.

```bash
git clone https://github.com/insightitsGit/prismrag.git
cd prismrag/examples/graph-rag-replacement
pip install -r requirements.txt
python demo_taxonomy_connection.py
pytest test_demo.py -v
```

**Live folder:** https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement  
**Scorecard:** https://github.com/insightitsGit/prismrag/blob/main/docs/taxonomy-scorecard.md  
**Pages setup:** [`docs/GITHUB_PAGES_DEMO.md`](docs/GITHUB_PAGES_DEMO.md)

Soft CTA: reply **TAXONOMY** (issue / DM / email `prismrag@insightits.com`) with a redacted mapping JSON or demo `SUMMARY` for an async one-page connection map — **no calendar**.

---

## Quick start (library)

```python
from prismrag_patch import PrismRAG

mapping = {
    "categories": [
        {"slug": "risk", "label": "Risk & Compliance"},
        {"slug": "growth", "label": "Growth & Revenue"},
    ],
    "rules": [
        {"word": "volatility", "category_slug": "risk"},
        {"word": "drawdown", "category_slug": "risk"},  # same category → rule edge
        {"word": "revenue", "category_slug": "growth"},
    ],
}

rag = PrismRAG(mapping=mapping, tenant_id="demo")
rag.ingest(records=[
    {"word": "volatility", "text": "Market volatility spiked in Q3 amid rate uncertainty."},
    {"word": "drawdown", "text": "Portfolio drawdown exceeded the 10 percent risk budget."},
    {"word": "revenue", "text": "Q3 revenue beat estimates on enterprise ARR growth."},
])

hits = rag.search("What are the risk metrics for the portfolio?", top_k=5)
for h in hits["results"]:
    print(h["category_slug"], h["chunk_ref"], h["chunk_text"][:60])
```

Bring your own `embed_fn` in production (Gemini / OpenAI / local). The library ships deterministic embeddings for offline tests and CI.

**Verified install bench:** [`examples/demo_app`](examples/demo_app) — 13/13 tests vs PyPI 0.2.1. See [INFO.md](INFO.md#verified-benchmark-pypi-021).

---

## What ships in the library

| Capability | What it means |
|------------|----------------|
| **Tier-1 mapping** | Auditable word→category rules; every hit can trace to a rule |
| **Dual vectors** | 768-d semantic + 256-d personal projection |
| **Word graph** | Rule edges (same category) + optional semantic edges |
| **Louvain communities** | Topic clusters for Graph RAG routing |
| **Graph RAG search** | Community seed → BFS → re-rank · `category_filter` supported |
| **Bridges** | `create_bridge(a, b)` for cross-community hops |
| **Append** | New chunks / rules without full retrain · chunk quality scores |
| **Stores** | `MemoryStore` (default) · `PostgresStore` (`prismrag.*`) |
| **Adapters** | Tier-1 remap onto pgvector / Chroma / Pinecone / Weaviate |

```
Your app
  └─ PrismRAG
       ├─ ingest → map → dual embed → graph → communities
       ├─ search → graph_rag | direct fallback
       ├─ create_bridge / append_chunks / chunk_quality
       └─ MemoryStore | PostgresStore | vector adapters
```

---

## Who it’s for

- Eng teams who need **controlled connections** between base chunks — not corpus lottery  
- Regulated domains (healthcare, finance, legal) where retrieval must explain **which rule** applied  
- Multi-tenant / consultancy setups: **same docs → different graphs** per client mapping  
- Anyone tired of bolting a second Graph RAG product onto an existing vector store  

### Domain sketches

| Domain | Mapping idea |
|--------|----------------|
| Healthcare | `medication` vs `lab_results` — “insulin management” stays on meds, not random co-symptoms |
| Finance | `risk` vs `growth` — VaR / volatility stay in risk even when embeddings blur |
| Enterprise KB | Each BU ships a mapping JSON; one SharePoint dump → many tenant graphs |

---

## Install

```bash
pip install prismrag-patch                      # core
pip install "prismrag-patch[graph]"             # + Louvain (recommended)
pip install "prismrag-patch[graph,pgvector]"    # + PostgresStore + pgvector
pip install "prismrag-patch[all]"               # all optional deps
```

Python 3.9+. No license key. Core path needs no network.

| Backend | When |
|---------|------|
| **MemoryStore** | Notebooks, tests, smoke demo |
| **PostgresStore** | Production — [`prismrag/schema.sql`](prismrag/schema.sql) |
| **Vector adapters** | Remap only — keep your existing chunk table |

Full API matrix: [`prismrag_patch/README.md`](prismrag_patch/README.md).

---

## Repo layout

| Path | Purpose |
|------|---------|
| [`prismrag_patch/`](prismrag_patch/) | **PyPI package** — ship this |
| [`docs/demo.html`](docs/demo.html) | **Interactive Pages demo** (PrismGuard-style walkthrough) |
| [`docs/taxonomy-scorecard.md`](docs/taxonomy-scorecard.md) | Self-serve scorecard · soft CTA **TAXONOMY** |
| [`examples/graph-rag-replacement/`](examples/graph-rag-replacement/) | **CLI smoke demo** — Graph RAG replacement proof |
| [`examples/demo_app/`](examples/demo_app/) | PyPI install verification + 13 tests |
| [`INFO.md`](INFO.md) | Landing / FAQ / product canon |
| [`prismrag/`](prismrag/) | Legacy SaaS API (archived reference) |
| [`tests/test_lib_*.py`](tests/) | Library parity (CI) |

---

## Development

```bash
pip install -e "prismrag_patch[graph]"
pytest tests/test_lib_step*.py -v

cd examples/graph-rag-replacement && pip install -r requirements.txt
python demo_taxonomy_connection.py && pytest test_demo.py -v

cd examples/demo_app && python run_verification.py
```

---

## Publish

Published: **0.2.1**. Next bump: `prismrag_patch/pyproject.toml` + [`DOC/pypi-publish.md`](DOC/pypi-publish.md).

---

## License

Apache-2.0 — [`prismrag_patch/LICENSE`](prismrag_patch/LICENSE).

---

`voice:research-b2b` · soft CTA **TAXONOMY** · never cold Calendly · proof only from smoke demo + published INFO benches
