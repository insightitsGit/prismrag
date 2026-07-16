# PrismRAG — taxonomy-grounded Graph RAG (open source)

**Stop RAG category bleed.** Define your mapping (categories + word→category rules); PrismRAG ingests data into *your* vector space, builds a graph on *your* taxonomy, and runs Graph RAG search with a full audit trail.

[![PyPI](https://img.shields.io/pypi/v/prismrag-patch)](https://pypi.org/project/prismrag-patch/0.2.1/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](prismrag_patch/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/prismrag-patch)](https://pypi.org/project/prismrag-patch/)

```bash
pip install "prismrag-patch[graph]"
```

📄 **[INFO.md](INFO.md)** — product overview, benchmark results, FAQ, landing-page copy.

**Maintained by:** [Insight IT Solutions](https://insightits.com) · **PyPI:** [`prismrag-patch` 0.2.1](https://pypi.org/project/prismrag-patch/0.2.1/) (published)

---

## Why PrismRAG?

| Problem with standard RAG / Graph RAG | PrismRAG approach |
|--------------------------------------|-------------------|
| Wrong category in retrieval (“category bleed”) | Every chunk assigned from **your mapping rules** |
| Graph from document co-occurrence | Graph from **your taxonomy** + semantic edges |
| Black-box retrieval | Every hit traces to a **mapping_rule** |
| Hosted platform lock-in | **`pip install`**, MemoryStore or your Postgres |
| Per-seat / API metering | **Free** Apache-2.0 library |

You supply the **mapping table**. The library does the rest: dual-vector projection, word graph, Louvain communities, Graph RAG search, bridges, append, and quality scoring.

---

## Quick start

```python
from prismrag_patch import PrismRAG

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

rag = PrismRAG(mapping=mapping, tenant_id="demo")
rag.ingest(records=[
    {"word": "metformin", "text": "metformin for diabetes"},
    {"word": "troponin",  "text": "troponin cardiac marker"},
])

for hit in rag.search("diabetes medications", top_k=5)["results"]:
    print(hit["category_slug"], hit["chunk_ref"])
```

**Verified benchmark:** [`examples/demo_app`](examples/demo_app) — 13/13 tests vs PyPI 0.2.1, ~0.8s full run. See [INFO.md](INFO.md#verified-benchmark-pypi-021).

---

## Use cases

### Healthcare & clinical informatics

Map `diagnosis`, `medication`, `lab_results`, `symptoms`, `patient_safety`. Query *“insulin management”* returns medication-category chunks — not random co-occurring symptoms. Required when EHR/RAG systems must explain **why** a document was retrieved.

### Finance, risk & compliance

Categories: `risk`, `valuation`, `liquidity`, `regulatory`. Keep *VaR*, *volatility*, and *exposure* in **risk** even when embeddings blur finance vs growth language. Audit trail from rule → chunk → search result for regulators.

### Pharmacy & life sciences

Separate `drug_interactions`, `pharmacokinetics`, `storage`, `contraindications`. Prevents cross-contamination in agent retrieval (e.g. storage conditions mixed with dosing advice).

### Enterprise knowledge bases

Each business unit submits a mapping JSON; the **same SharePoint or Confluence export** yields **different graphs** per unit. Consultants white-label per client without re-ingesting into a shared SaaS.

### AI agents & production RAG

Use `PrismRAG` in-process or `PostgresStore` on your DB. Optional **pgvector / Chroma / Pinecone / Weaviate** adapters for Tier-1 remap on existing vector stores. Bring your own `embed_fn` (OpenAI, Gemini, local models).

### Regulated & high-stakes domains

Legal, insurance, government: enforce **hard category boundaries** at retrieval (`category_filter`) and export dual vectors for downstream agents — no data leaves your environment unless you choose.

---

## Your mapping drives everything

```python
# From JSON, CSV, Excel, or your SQL table — build this dict:
mapping = {"categories": [...], "rules": [{"word": "...", "category_slug": "..."}]}
rag = PrismRAG(mapping=mapping, tenant_id="acme")
```

| Backend | When to use |
|---------|-------------|
| **MemoryStore** (default) | Notebooks, tests, prototypes |
| **PostgresStore** | Production — `prismrag.*` schema ([`prismrag/schema.sql`](prismrag/schema.sql)) |
| **Vector adapters** | Tier-1 remap only on existing pgvector / Chroma / Pinecone / Weaviate |

See [`prismrag_patch/README.md`](prismrag_patch/README.md) for Postgres, adapters, and API parity matrix.

---

## Repo layout

| Path | Purpose |
|------|---------|
| [`prismrag_patch/`](prismrag_patch/) | **PyPI package** — ship this |
| [`examples/demo_app/`](examples/demo_app/) | PyPI install demo + 13 integration tests + event logs |
| [`examples/graph-rag-replacement/`](examples/graph-rag-replacement/) | Taxonomy mapping → rule edges → dual retrieve (Graph RAG replacement proof) |
| [`prismrag/`](prismrag/) | Legacy SaaS API (archived, not deployed) |
| [`tests/test_lib_*.py`](tests/) | Library parity tests (CI) |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI build + test |

---

## Development

```bash
pip install -e "prismrag_patch[graph]"
pytest tests/test_lib_step*.py -v
```

```bash
cd examples/demo_app && python run_verification.py
```

```bash
cd examples/graph-rag-replacement
pip install -r requirements.txt
python demo_taxonomy_connection.py
pytest test_demo.py -v
```

---

## Publish to PyPI

Already published: **0.2.1**. For next release, bump `prismrag_patch/pyproject.toml` and run `twine upload`. See [`DOC/pypi-publish.md`](DOC/pypi-publish.md).

---

## License

Apache-2.0 — see [`prismrag_patch/LICENSE`](prismrag_patch/LICENSE).
