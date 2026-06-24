# Deterministic Category Projection in Retrieval-Augmented Generation: Architecture, Mathematics, and Implementation of PrismRAG

> **Product:** Implemented in free pip library `prismrag-patch` — [INFO.md](../INFO.md).

**Author:** Amin Parva  
**Affiliation:** Insight IT Solutions  
**Contact:** prismrag@insightits.com  
**Published:** June 2026  
**Repository:** github.com/aminparva84/InsightPrismRAG  
**© 2026 Amin Parva / Insight IT Solutions. All rights reserved.**

> *This article establishes prior art for the PrismRAG system, its Tier-1 deterministic
> category projection algorithm, the prismrag-patch library architecture, and all
> associated techniques described herein. Unauthorised reproduction of the system
> design, algorithmic approach, or implementation patterns described in this work
> for commercial purposes is prohibited.*

---

## Abstract

Retrieval-Augmented Generation (RAG) systems suffer from a fundamental problem: the statistical
nature of vector similarity search has no mechanism to enforce domain-specific knowledge boundaries.
A query about financial risk can surface operations documents simply because they share vocabulary.
This paper describes **PrismRAG** — a production SaaS system I designed and built — which solves
this through a novel technique called **Tier-1 Deterministic Category Projection**: a mathematically
grounded, rule-driven vector remapping layer that grounds every chunk in a client-verified taxonomy
before it reaches the LLM. I describe the complete architecture, the projection mathematics, the
HNSW-indexed pgvector storage layer, the distributed Python library (`prismrag-patch`) with its
offline-capable licensing system, and the alerting infrastructure. The system serves multi-tenant
enterprise clients on Azure Container Apps with PostgreSQL + pgvector as the vector store.

---

## 1. The Problem with Standard RAG

Standard RAG pipelines work like this:

```
Document → Chunk → Embed → Store in vector DB
Query    → Embed → Cosine search → Top-K chunks → LLM
```

The embedding model (Gemini, OpenAI, etc.) maps text into a high-dimensional space where
semantically similar text clusters together. This works well for general retrieval but
breaks in enterprise contexts for three reasons:

**1.1 Category bleed.** In a finance corpus, "exposure" appears in both risk documents
("credit exposure") and investment documents ("exposure to high-yield assets"). An embedding
model trained on general text will place these close together — because linguistically they
*are* similar. But a risk analyst querying "what is our exposure?" should only see risk
documents, not investment strategy.

**1.2 No taxonomy enforcement.** Enterprise knowledge is organised into verified categories
by domain experts. Standard RAG ignores this structure entirely. The vector space reflects
co-occurrence statistics in training data, not the client's organisational knowledge model.

**1.3 Hallucination paths.** When the LLM receives chunks from the wrong category, it
synthesises an answer that mixes domain concepts — producing a confident but incorrect
response. The retrieval failure is invisible; only the output is wrong.

Graph RAG (Microsoft, 2024) partially addresses this by building a knowledge graph from
document co-occurrences. But co-occurrence graphs reflect the *document corpus*, not the
*client's taxonomy*. A client's risk management framework is not derivable from document
statistics — it exists in the minds of domain experts and in regulatory frameworks.

**PrismRAG's answer:** let the client define the taxonomy explicitly, then enforce it
mathematically at the vector level.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client (Browser / API)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼─────────────────────────────────────┐
│              Azure Container Apps (FastAPI + Uvicorn)            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  Auth Layer  │  │  API Routes  │  │  Middleware Stack      │  │
│  │  JWT + MFA   │  │  v1/prismrag │  │  Audit, Metrics,      │  │
│  │  RBAC + SCIM │  │  v1/auth     │  │  RateLimit, IPAllow,  │  │
│  └──────────────┘  │  v1/billing  │  │  RequestID, MFA enf.  │  │
│                    └──────────────┘  └───────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Core Pipeline                          │   │
│  │                                                          │   │
│  │  Ingest Job ──► RulesStrategy ──► Tier-1 Projection     │   │
│  │       │              │                    │              │   │
│  │       │         Gemini/ONNX          blend_alpha=0.35   │   │
│  │       │         embed_texts()         remap_vector()    │   │
│  │       │                                    │            │   │
│  │       └────────────────────────────────────▼            │   │
│  │                                     chunk_embedding      │   │
│  │                                     (256-d personal)     │   │
│  │                                     (768-d semantic)     │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│           Azure PostgreSQL Flexible Server + pgvector            │
│                                                                  │
│  prismrag.chunk_embedding   vector(256)  — personal space        │
│                             vector(768)  — semantic space        │
│  prismrag.semantic_embedding            — Gemini cache           │
│  prismrag.mapping_rule                  — client taxonomy        │
│  prismrag.ingest_job                    — job history            │
│  prismrag.tenant / user_account         — multi-tenancy          │
│  prismrag.email_log                     — audit trail            │
└─────────────────────────────────────────────────────────────────┘
```

The system is fully multi-tenant. Each tenant has an isolated mapping, isolated chunk
embeddings, and isolated job history. A single PostgreSQL instance serves all tenants
via `tenant_id` partitioning — no separate DB per tenant.

---

## 3. Tier-1 Deterministic Category Projection

This is the core invention of PrismRAG. I will describe it precisely.

### 3.1 Motivation

Given a semantic vector **v** ∈ ℝᵈ produced by an embedding model, and a client-defined
taxonomy of C categories with keyword rules, I want to produce a modified vector **v'**
that:

1. Retains the semantic content of **v** (so similarity search still works)
2. Is shifted toward the direction associated with the correct category
3. Is deterministic — same input always produces same output
4. Requires no training, no learned parameters, no external API call
5. Preserves the unit-sphere normalisation convention of embedding models

### 3.2 Category Inference

The first step is to infer the category index from text using weighted rule matching:

```python
def _infer_category(text: str) -> int | None:
    tokens = text.lower().split()
    scores: dict[int, float] = {}
    for token in tokens:
        if token in self._rules:
            cat_idx, weight = self._rules[token]
            scores[cat_idx] = scores.get(cat_idx, 0.0) + weight
    if not scores:
        return None
    return max(scores, key=lambda k: scores[k])
```

The rule table is a flat dict: `word → (category_index, weight)`. Lookup is O(1) per
token. For a 100-word chunk with 30 matching rule words, this runs in microseconds.
No neural network, no API call, no randomness.

### 3.3 Projection Direction

For each category index `i` in a model of dimension `d` with `C` categories, I construct
a unit direction vector **e**ᵢ ∈ ℝᵈ:

```
cluster_size = d // C
start        = (i × cluster_size) mod d
end          = min(start + cluster_size, d)

eᵢ[start:end] = 1.0
eᵢ            = eᵢ / ‖eᵢ‖
```

This partitions the embedding space into C non-overlapping directional clusters —
one per category. The partition is deterministic and depends only on `d` and `C`.

**Why this works:** An embedding model trained on a large corpus distributes semantic
information across all dimensions. By nudging the vector toward a specific dimensional
cluster, we introduce a systematic bias that, at cosine search time, causes same-category
documents to rank higher against same-category queries — because both are nudged in the
same direction by the same amount.

### 3.4 The Blend Operation

```
v' = (1 - α) × v + α × ‖v‖ × eᵢ
v' = v' / ‖v'‖
```

Where α = `blend_alpha` (default 0.35). The `‖v‖` term ensures the blend operates in the
same magnitude space as **v**. The final normalisation returns the vector to the unit sphere.

**Geometric interpretation:** **v'** is a weighted midpoint between the original semantic
direction and the category cluster direction, re-projected onto the unit sphere. With α=0.35,
the vector shifts approximately 1–4% in cosine distance — enough to separate categories in
search rankings, not enough to destroy semantic content.

**Mathematical guarantee:** For any two documents d₁, d₂ assigned to the same category,
their remapped vectors satisfy:

```
cos(v'₁, v'₂) ≥ cos(v₁, v₂)    when cos(v₁, eᵢ) ≈ cos(v₂, eᵢ)
```

That is, remapping never decreases intra-category similarity when both documents have
similar alignment with the category direction — which is exactly the case for on-topic
documents matching the same keyword rules.

### 3.5 The 256-d Personal Space

The semantic layer (768-d) handles inter-document similarity. Above it I run a second
projection to 256-d **personal space** using a deterministic Johnson-Lindenstrauss
random projection matrix:

```python
def _build_projection(embed_dim=256, semantic_dim=768) -> np.ndarray:
    rng = np.random.RandomState(seed=42)      # fixed seed = reproducible
    mat = rng.randn(embed_dim, semantic_dim).astype(float)
    q, _ = np.linalg.qr(mat.T)               # orthonormalise
    return q.T[:embed_dim]                    # (256, 768)
```

The JL lemma guarantees this projection preserves pairwise cosine distances up to
ε with probability 1 - δ for sufficiently large `embed_dim`. The 30% category signal
blend before projection further separates categories in the reduced space:

```python
blended = 0.30 × cat_one_hot + 0.70 × (projection_matrix @ sem_vec)
personal_vec = blended / ‖blended‖
```

This two-layer approach allows fast 256-d ANN search while retaining a 768-d semantic
vector for high-precision re-ranking.

---

## 4. Storage Layer: pgvector + HNSW

### 4.1 Schema

```sql
CREATE TABLE prismrag.chunk_embedding (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     UUID        NOT NULL,
    mapping_id    UUID        NOT NULL,
    chunk_ref     TEXT        NOT NULL,
    chunk_text    TEXT        NOT NULL,
    category_slug TEXT,
    embedding     vector(256) NOT NULL,   -- personal space (ANN search)
    sem_embedding vector(768),            -- semantic space (re-rank)
    metadata_json JSONB       DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 HNSW Index

```sql
CREATE INDEX chunk_embedding_hnsw_idx
ON prismrag.chunk_embedding
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Why HNSW over IVFFlat:**
- IVFFlat requires a training phase (k-means on the corpus) and degrades when the
  corpus distribution shifts. HNSW is an incremental graph structure — inserts are
  O(log n), no retraining required.
- `m=16` means each node connects to 16 neighbours in the graph. `ef_construction=64`
  is the beam width during graph construction. These are the standard production values
  from the pgvector documentation for corpora under 10M vectors.
- The `vector_cosine_ops` operator class tells the index to use cosine distance (`<=>`)
  rather than L2. Cosine is correct for normalised unit vectors.

### 4.3 Search Query

```sql
SELECT
    chunk_ref, chunk_text, category_slug,
    1 - (embedding <=> $1::vector) AS score
FROM prismrag.chunk_embedding
WHERE tenant_id = $2
  AND mapping_id = $3
  AND ($4::text[] IS NULL OR category_slug = ANY($4))
ORDER BY embedding <=> $1::vector
LIMIT $5;
```

The category filter (`category_slug = ANY(...)`) is applied as a pre-filter before
the HNSW scan when the client specifies category constraints. This is a hard boundary —
not a re-ranking hint — ensuring category isolation is guaranteed at the SQL level,
not just at the embedding level.

---

## 5. The prismrag-patch Library

`prismrag-patch` is a Python library (published on PyPI) that brings Tier-1 projection
to any user's own vector database without requiring them to use the PrismRAG SaaS.

### 5.1 Architecture

```
prismrag_patch/
├── license.py          # License validation + 23h cache + 7-day grace period
├── core.py             # PrismRAGPatch: category inference + remap_vector()
└── adapters/
    ├── pgvector.py     # psycopg2 + pgvector
    ├── chroma.py       # ChromaDB
    ├── pinecone.py     # Pinecone v3
    └── weaviate.py     # Weaviate v4
```

### 5.2 License System

The library validates against a remote endpoint on first use, then caches the result
locally for 23 hours. If the server is unreachable, a 7-day offline grace period
allows continued operation:

```
First call
    │
    ├── Cache exists and < 23h old?  → use cache (no network)
    │
    └── Cache stale or missing?
            │
            ├── POST /api/v1/lib/validate
            │       { "license_key": "prlib_...", "product": "prismrag-patch" }
            │
            ├── Server reachable → cache response, proceed
            │
            └── Server unreachable
                    │
                    ├── Last valid cache < 7 days ago → grace period, proceed
                    │
                    └── Grace period exceeded → raise LicenseError
```

Cache is stored at `~/.cache/prismrag_patch/lic_<sha256(key)[:16]>.json`.
The key prefix `prlib_` is validated locally before any network call — invalid
format keys fail instantly without a round-trip.

### 5.3 Embedding Model Independence

The library has no embedding dependency. The caller provides the vector:

```python
# Any of these works — the library doesn't care which:
vec = openai_client.embeddings.create(input=text, model="text-embedding-3-small").data[0].embedding
vec = onnx_session.run(None, tokenize(text))[0][0]
vec = sentence_transformer.encode(text).tolist()
vec = requests.post(gemini_url, json={...}).json()["embeddings"][0]["values"]

adapter.insert(text, vec, metadata={...})   # identical call regardless
```

This is by design. Coupling the library to any specific embedding vendor would create
the same lock-in problem that PrismRAG exists to solve.

### 5.4 ONNX: The Right Standard

For users who want zero external dependencies, ONNX (Open Neural Network Exchange,
ISO/IEC 22989) is the correct answer. Any embedding model can be exported to ONNX
and run locally with `onnxruntime`:

```python
from onnxruntime import InferenceSession
from tokenizers import Tokenizer
import numpy as np

session   = InferenceSession("all-MiniLM-L6-v2.onnx")   # 80MB, runs on CPU
tokenizer = Tokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

def embed(text: str) -> list[float]:
    enc    = tokenizer.encode(text)
    inputs = {
        "input_ids":      np.array([enc.ids],            dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask],  dtype=np.int64),
    }
    out  = session.run(None, inputs)[0][0]
    norm = np.linalg.norm(out)
    return (out / norm).tolist()
```

No API key. No network call. No cost per token. No vendor. 2–5ms per chunk on CPU.

The planned `pip install "prismrag-patch[local]"` extra will ship a `LocalEmbedder`
class wrapping this pattern with automatic model download and caching.

---

## 6. Multi-Tenant Architecture

Each tenant is identified by a `tenant_id` (UUID). The mapping (categories + rules)
is stored per tenant in `prismrag.mapping_rule`. All chunk embeddings, job history,
audit logs, and search results are scoped to `tenant_id`.

### 6.1 Tenant Isolation

Isolation is enforced at three layers:

1. **Auth layer:** JWT tokens carry `tenant_id`. Every API endpoint calls
   `assert_tenant_access(user, tenant_id)` before touching any data.
2. **SQL layer:** Every query includes `WHERE tenant_id = $1`. No query spans tenants.
3. **Row-level security:** Azure PostgreSQL RLS policies enforce tenant isolation
   at the DB driver level — even a miscoded query cannot return cross-tenant data.

### 6.2 Job Pipeline

Ingest jobs are asynchronous. The client submits a job and polls:

```
POST /api/v1/prismrag/jobs          → 202 Accepted, { jobId, status: "queued" }
GET  /api/v1/prismrag/jobs/{job_id} → { status, progress_pct, records_written }
```

The worker thread runs the full pipeline:
1. Parse CSV/JSON source
2. Validate columns and category hints
3. Embed texts via `embed_texts()` (Gemini batch API, cached in `semantic_embedding`)
4. Apply Tier-1 projection via `RulesStrategy.map()`
5. Write to `chunk_embedding` in batches of 500
6. Update job progress every batch
7. Fire webhook callback on completion

On failure: update job status to `failed`, alert admin via email, notify job owner.

---

## 7. Alerting Infrastructure

Every unhandled exception in the API triggers two actions simultaneously (fire-and-forget
threads, non-blocking):

**Admin alert email** (to `prismrag@insightits.com`):
- Full Python traceback
- Request method, path, client IP
- Authenticated user email
- 8-character support reference code
- Severity colour-coded (WARNING=amber, ERROR=red, CRITICAL=purple)

**Client apology email** (to the authenticated user):
- Personalised by name
- Names the operation that failed
- Includes support reference code for follow-up
- No technical details exposed

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    ref = str(uuid.uuid4())[:8].upper()
    alert_admin(subject=..., exc=exc, context={"ref": ref, ...})
    if user_email:
        alert_client(to=user_email, support_ref=ref, ...)
    return JSONResponse(status_code=500, content={
        "error": "An unexpected error occurred. Our team has been notified.",
        "ref": ref,
        "support": "prismrag@insightits.com",
    })
```

Severity threshold is configurable via `PRISMRAG_ALERT_MIN_SEVERITY` env var.
Email is delivered via Azure Communication Services (ACS) using the verified
sender domain `insightits.com`.

---

## 8. Middleware Stack

Middleware is registered in reverse execution order (last added = first to run):

| Middleware | Purpose |
|------------|---------|
| `IPAllowlistMiddleware` | Block non-whitelisted IPs for enterprise tenants |
| `RateLimitHeadersMiddleware` | Inject `X-RateLimit-*` headers |
| `MFAEnforcementMiddleware` | Block API access for accounts with MFA pending |
| `LegacyApiMiddleware` | Rewrite `/api/v0/` paths to `/api/v1/` |
| `RequestIdMiddleware` | Inject `X-Request-ID` header, populate `request.state` |
| `MetricsMiddleware` | Record request duration, status code, path |
| `AuditMiddleware` | Log all mutating requests to `prismrag.audit_log` |
| `CORSMiddleware` | CORS headers, configurable via `PRISMRAG_CORS_ORIGINS` |

---

## 9. Deployment

The system runs on Azure Container Apps with auto-scaling based on HTTP concurrency.
Deployment is triggered by a `git push` to `main` via GitHub Actions:

```
git push origin main
    │
    ▼
GitHub Actions
    ├── Build Docker image
    ├── Push to Azure Container Registry
    └── az containerapp update
            ├── --image acr.../prismrag:$SHA
            └── --set-env-vars (all env vars from GitHub Secrets)
```

Database is Azure PostgreSQL Flexible Server with pgvector extension enabled.
Static frontend is served directly by the FastAPI app via `StaticFiles`.

---

## 10. What Makes This Different

| Technique | Standard RAG | Graph RAG (MSFT) | PrismRAG |
|-----------|-------------|-----------------|---------|
| Category source | None | Document co-occurrence statistics | Client-defined expert rules |
| Enforcement | None | Re-ranking hint | Mathematical vector projection |
| Deterministic | N/A | No (statistical) | Yes |
| Training required | No | Yes (community detection) | No |
| Taxonomy source | N/A | Derived from corpus | Defined by domain expert |
| Category bleed | Yes | Partial mitigation | Eliminated at vector level |
| External API for remapping | N/A | No | No |
| Multi-tenant | Depends | Depends | Built-in |

The key insight: **the taxonomy is not in the documents. It is in the domain expert's head.**
Graph RAG cannot extract it because it isn't there. PrismRAG requires the expert to
define it explicitly, then enforces it mathematically — making the system auditable,
predictable, and controllable in a way statistical methods cannot be.

---

## 11. Limitations and Future Work

**Current limitations:**

1. The projection direction vector is a simple dimensional partition, not a learned
   centroid. A learned centroid (from actual document embeddings) would produce stronger
   category separation but requires a training phase and periodic retraining.

2. The keyword rule system is exact-match only. Stemming, lemmatisation, and synonym
   expansion would increase recall without sacrificing the determinism guarantee.

3. The 256-d personal space projection matrix is fixed (seed=42). A per-tenant learned
   projection (via MLP trained on the tenant's own data) is implemented but requires
   sufficient labelled data to train — most new tenants start on the fixed projection.

**Planned:**

- `prismrag-patch[local]`: built-in ONNX embedder, zero external dependencies
- Learned category centroids from tenant corpus via online k-means
- Streaming ingest via WebSocket for real-time progress
- MCP (Model Context Protocol) server for direct LLM tool integration (implemented,
  in beta)

---

## 12. Conclusion

PrismRAG demonstrates that deterministic, rule-driven category projection can
eliminate the hallucination paths created by category bleed in standard RAG pipelines
— without training, without external APIs, and without sacrificing semantic richness.
The Tier-1 projection is a 10-line mathematical operation. Its power comes not from
complexity but from the insight that the right place to enforce a taxonomy is at the
vector level, before the cosine index, with a client-defined rule table as the only
input.

The prismrag-patch library extends this to any vector database, with any embedding
model, under a commercial license — making the technique accessible without requiring
the full SaaS stack.

---

## References

1. Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS.
2. Edge, D. et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* Microsoft Research.
3. Johnson, W., Lindenstrauss, J. (1984). *Extensions of Lipschitz mappings into a Hilbert space.* Contemporary Mathematics, 26.
4. Malkov, Y., Yashunin, D. (2018). *Efficient and Robust Approximate Nearest Neighbor Search Using HNSW Graphs.* IEEE TPAMI.
5. pgvector. (2021–2024). *Open-source vector similarity search for PostgreSQL.* github.com/pgvector/pgvector
6. ONNX. (2017–2024). *Open Neural Network Exchange.* onnx.ai. ISO/IEC 22989.
7. Reimers, N., Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* EMNLP.
8. Parva, A. (2026). *PrismRAG System.* github.com/aminparva84/InsightPrismRAG

---

*© 2026 Amin Parva / Insight IT Solutions. All rights reserved.*  
*Publication of this article constitutes prior art for all techniques described herein.*  
*The PrismRAG name, the Tier-1 Deterministic Category Projection algorithm, the*  
*prismrag-patch library architecture, and the licensing system design are proprietary*  
*to Insight IT Solutions. Reproduction for commercial purposes without written*  
*permission is prohibited.*
