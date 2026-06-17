# PrismRAG — Technical Reference

## Vector spaces

PrismRAG maintains two vector spaces per chunk:

| Space | Dimension | Model | Purpose |
|---|---|---|---|
| Personal | 256-d | MLP or QR projection | Community membership, MLP re-rank |
| Semantic | 768-d | Gemini text-embedding-004 | Cross-tenant cosine similarity, community centroids |

Both are stored per chunk in `chunk_embedding` with HNSW indexes (`m=16, ef_construction=64`).

### Why 256-d personal space

The personal space is defined by the client's mapping. 256 dimensions is enough to separate ~50–200 distinct categories cleanly while keeping memory and HNSW index size manageable. At 1M chunks: `1M × 256 × 4 bytes = 1 GB` index in RAM — fits comfortably on a 2 GB worker.

---

## Tier 1: RulesStrategy

**Every word gets an assignment that traces to a row in `mapping_rule`.** This is the auditable path.

```python
# Projection: 768-d semantic → 256-d personal
# Uses QR decomposition of a seeded random matrix (deterministic, reproducible)
P = np.linalg.qr(rng.standard_normal((768, 256)))[0]   # seed=42 + category_id

# Blend: 30% category signal, 70% semantic content
category_vec = one_hot(category_index, n_categories)          # (n_categories,)
category_256 = category_vec @ W_cat                            # (256,) learned projection
blended = 0.30 * category_256 + 0.70 * (sem_vec @ P)
personal = blended / np.linalg.norm(blended)                  # L2 normalize
```

The 70/30 split means words in the same category cluster together (via the 30% signal) while retaining enough semantic content (70%) that "revenue" and "income" are still close even if in different categories.

---

## Tier 2: MLPStrategy

Architecture:
```
Input:  768-d Gemini embedding
Hidden: max(512, 2×256) = 512 units, GELU activation, LayerNorm, Dropout(0.1)
Hidden: 512 units, GELU, LayerNorm, Dropout(0.1)
Output: 256-d, L2 normalized
```

Loss function:
```python
# InfoNCE multi-positive (words in same category are positives)
L_infonce = -log( sum(exp(sim(a,p)/τ) for p in positives)
                / sum(exp(sim(a,x)/τ) for x in all_in_batch) )

# Anchor repulsion (push category centroids apart)
L_repulsion = mean(max(0, margin - dist(centroid_i, centroid_j))²)

L_total = L_infonce + 0.35 * L_repulsion
```

Training config: τ=0.20, repulsion weight=0.35, AdamW lr=3e-4, CosineAnnealingLR, 180 epochs, val holdout=last 2 words per category.

Validation target: recall@10 ≥ 0.85. Falls back to Tier-1 if not reached.

---

## Graph construction

### Rule edges
All word pairs within the same category get a rule edge (weight=1.0). For a category with N words: N×(N-1)/2 edges. Capped at 500 words per category to avoid O(N²) blowup.

### Semantic edges
For each word, find top-20 neighbors by cosine similarity in 768-d space. Add an edge if cosine ≥ 0.70. Semantic edges cross category boundaries — they represent genuine semantic overlap.

### Bridge edges (AP001.2)
```python
sem_bridge = normalize((centroid_A + centroid_B) / 2)
personal_bridge = mlp(sem_bridge)   # or deterministic projection
```
Bridge edges connect the `top_words` lists of both communities, creating a traversal path between them.

---

## HNSW indexes

Every vector column has:
```sql
CREATE INDEX USING hnsw (col vector_cosine_ops)
WITH (m=16, ef_construction=64);
```

| Parameter | Value | Effect |
|---|---|---|
| m=16 | 16 bidirectional links per node | Good recall/speed tradeoff |
| ef_construction=64 | Search width during build | Higher = better recall, slower build |

At query time, set `SET hnsw.ef_search = 100` for higher recall (default 40). For interactive search, 40 is fine. For batch evaluation, use 100.

---

## Metering architecture

```
Request arrives
  │
  ├─ Redis sliding window (60s)    ← check req/min limit
  │    key: rl:{user_id}
  │    ZREMRANGEBYSCORE + ZADD + ZCARD in one pipeline
  │    < 1 ms
  │
  ├─ Redis monthly counter          ← check chunk/search budget
  │    key: quota:{user_id}:{event}:{YYYY-MM}
  │    INCR / GET
  │    < 1 ms
  │    Postgres fallback if Redis unavailable
  │
  ▼
  Handler runs
  │
  └─ Background thread              ← write usage_event to Postgres
       never blocks response
```

Over quota returns HTTP 402 with structured body:
```json
{
  "error": "quota_exceeded",
  "event_type": "search",
  "used": 20000,
  "limit": 20000,
  "overage_price": "$1.50 per 1,000 units",
  "upgrade_url": "/dashboard.html#billing"
}
```

---

## Audit log retention

| Plan | api_request_log | search_result_log | ingest_result_log |
|---|---|---|---|
| free | 7 days | 7 days | 7 days |
| starter | 30 days | 30 days | 30 days |
| professional | 30 days | 30 days | 30 days |
| enterprise | 90 days | 90 days | 90 days |

Cleanup runs nightly at 02:00 UTC via Azure Container Apps scheduled job (`python -m prismrag.worker.cleanup`).

---

## Large file processing

| File size | Path | Memory on API server |
|---|---|---|
| < 1 MB | Inline in request handler | Full file |
| 1 MB – 500 MB | Blob SAS → Service Bus → worker downloads | Zero |
| > 500 MB | Blob SAS → Service Bus → worker streams row-by-row | One batch (256 rows) |

Streaming implementation: `BlobClient.download_blob().chunks()` wrapped in `io.TextIOWrapper` → `csv.DictReader`. Each 256-row batch is embedded, assigned, and flushed to Postgres before the next batch is read.

---

## Database connection pooling

`psycopg2.pool.ThreadedConnectionPool`:
- min connections: 2
- max connections: 10 (per process)

With 4 uvicorn workers (Dockerfile CMD), total max = 40 connections to Postgres. Azure Postgres Flexible Server default max_connections = 50 on B2s. If you add more replicas, use PgBouncer in front of Postgres (transaction mode, pool_size=20).

---

## Gemini embedding cache

All Gemini API calls are cached in `prismrag.semantic_embedding`:
```sql
SELECT embedding FROM prismrag.semantic_embedding WHERE text_hash = sha256(text)
```

Cache hit rate in practice: ~60–80% for ingest (many repeated words across jobs). Miss → Gemini API call → cache write. Batch size = 64 texts per Gemini call.

Cost at $0.00004/1K chars (Gemini text-embedding-004): 1M word ingests with 80% cache hit = 200K Gemini calls × avg 20 chars = ~$0.16. Negligible.
