# prismrag-patch

**Drop-in hallucination-resistant retrieval for your own vector database.**

Official site: **[prismrag.insightits.com](https://prismrag.insightits.com)** ·
PyPI: **[pypi.org/project/prismrag-patch](https://pypi.org/project/prismrag-patch/)** ·
Whitepaper: **[Deterministic Category Projection (PDF)](https://prismrag.insightits.com/whitepaper.html)**

PrismRAG Patch wraps pgvector, ChromaDB, Pinecone, or Weaviate with PrismRAG's
Tier-1 re-mapping technique — deterministic category projection that grounds every
chunk in your verified taxonomy before it ever reaches the LLM.

Works with **any embedding model** — Gemini, OpenAI, Cohere, HuggingFace, or your
own local model. No lock-in.

## Requirements

| Requirement | Detail |
|-------------|--------|
| Python | 3.10+ |
| License key | `prlib_` key from [prismrag.insightits.com](https://prismrag.insightits.com/prismrag-lib.html) |
| Embedding model | Any model that returns a list of floats — you provide the vector |

> **prismrag-patch does not generate embeddings.** You call your embedding model
> of choice, then pass the resulting vector to the adapter. The library remaps,
> enriches, and stores/searches it in your database.

## Quick start

```python
from prismrag_patch import PrismRAGPatch
from prismrag_patch.adapters.pgvector import PgvectorAdapter
import psycopg2

# ── 1. Your embedding function — use any model ────────────────────────────────

# Option A: OpenAI
from openai import OpenAI
def embed(text):
    return OpenAI().embeddings.create(
        input=text, model="text-embedding-3-small"
    ).data[0].embedding   # 1536-dim

# Option B: Gemini
import os, requests
def embed(text):
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-embedding-001:batchEmbedContents?key={os.environ['GEMINI_API_KEY']}",
        json={"requests": [{"model": "models/gemini-embedding-001",
                             "content": {"parts": [{"text": text}]},
                             "outputDimensionality": 768}]},
        timeout=30,
    )
    return resp.json()["embeddings"][0]["values"]   # 768-dim

# Option C: HuggingFace (local, no API key)
from sentence_transformers import SentenceTransformer
_model = SentenceTransformer("all-MiniLM-L6-v2")
def embed(text):
    return _model.encode(text).tolist()   # 384-dim


# ── 2. Define your category mapping ──────────────────────────────────────────
mapping = {
    "categories": [
        {"slug": "risk",   "label": "Risk and Compliance"},
        {"slug": "growth", "label": "Revenue and Growth"},
    ],
    "rules": [
        {"word": "volatility", "category_slug": "risk",   "weight": 1.0},
        {"word": "fraud",      "category_slug": "risk",   "weight": 1.0},
        {"word": "revenue",    "category_slug": "growth", "weight": 1.0},
        {"word": "earnings",   "category_slug": "growth", "weight": 1.0},
    ],
}

# ── 3. Initialize and connect ─────────────────────────────────────────────────
patch   = PrismRAGPatch(license_key="prlib_YOUR_KEY_HERE", mapping=mapping)
conn    = psycopg2.connect("postgresql://user:pass@localhost:5432/mydb")
adapter = PgvectorAdapter(patch, conn, table="my_chunks")
adapter.ensure_table(dim=768)   # match your model's output dimension

# ── 4. Embed with your model, insert with prismrag-patch ─────────────────────
doc    = "Market volatility spiked due to fraud risk exposure."
vec    = embed(doc)                        # your model produces the vector
row_id = adapter.insert(doc, vec, metadata={"source": "risk_report"})
# stored vector is remapped toward "risk" category cluster
# metadata gets prismrag_category + prismrag_label injected automatically

# ── 5. Search ─────────────────────────────────────────────────────────────────
query     = "what is our risk exposure?"
query_vec = embed(query)
results   = adapter.search(query, query_vec, top_k=5)
for r in results:
    print(r["score"], r["metadata"]["prismrag_category"], r["text"][:60])
```

## Batch insert

```python
records = [
    {"text": doc1, "vector": embed(doc1), "metadata": {"source": "q1"}},
    {"text": doc2, "vector": embed(doc2), "metadata": {"source": "q2"}},
]
ids = adapter.batch_insert(records)   # single transaction
```

## Installation

```bash
pip install prismrag-patch                   # core only
pip install "prismrag-patch[pgvector]"       # + pgvector (psycopg2)
pip install "prismrag-patch[chroma]"         # + ChromaDB
pip install "prismrag-patch[pinecone]"       # + Pinecone v3
pip install "prismrag-patch[weaviate]"       # + Weaviate v4
pip install "prismrag-patch[all]"            # all adapters
```

## Other adapters

### ChromaDB

```python
import chromadb
from prismrag_patch.adapters.chroma import ChromaAdapter

client     = chromadb.Client()
collection = client.get_or_create_collection("my_chunks")
adapter    = ChromaAdapter(patch, collection)
adapter.insert(doc, embed(doc), metadata={"source": "report"})
```

### Pinecone

```python
from pinecone import Pinecone
from prismrag_patch.adapters.pinecone import PineconeAdapter

pc      = Pinecone(api_key="YOUR_PINECONE_KEY")
index   = pc.Index("my-index")
adapter = PineconeAdapter(patch, index, namespace="finance")
adapter.insert(doc, embed(doc), metadata={"source": "report"})
```

### Weaviate

```python
import weaviate
from prismrag_patch.adapters.weaviate import WeaviateAdapter

client     = weaviate.connect_to_local()
collection = client.collections.get("MyChunks")
adapter    = WeaviateAdapter(patch, collection)
adapter.insert(doc, embed(doc))
```

## How it works

```
Your text
    │
    ▼
Any embedding model (OpenAI / Gemini / HuggingFace / Cohere / your own)
    │
    ▼
raw vector  [0.12, -0.45, 0.88, ...]   N dimensions
    │
    ▼
prismrag-patch.insert(text, raw_vector, metadata)
    │
    ├─ category inferred from your rules (local, deterministic, no API call)
    ├─ vector nudged toward winning category cluster (blend_alpha=0.35)
    └─ metadata enriched with prismrag_category + prismrag_label
    │
    ▼
stored in YOUR database — prismrag-patch never holds your data
```

## What prismrag-patch does NOT do

- Generate embeddings — you bring your own model
- Call an LLM
- Store your data on PrismRAG servers
- Lock you into any embedding provider

The only network call is a one-time license validation (cached 23 hours,
7-day offline grace period).

## License

Commercial license required. Get yours at
[prismrag.insightits.com/prismrag-lib.html](https://prismrag.insightits.com/prismrag-lib.html).

Questions? [prismrag@insightits.com](mailto:prismrag@insightits.com)

© 2026 Insight IT Solutions
