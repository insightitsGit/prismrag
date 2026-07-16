# Concepts

Each section: what it is · why it exists · when to use · common mistakes.

---

## Mapping

**What:** A dict (or `MappingConfig`) with `categories` and `rules`.

```python
{
  "categories": [{"slug": "risk", "label": "Risk & Compliance"}],
  "rules": [{"word": "volatility", "category_slug": "risk", "weight": 1.0}]
}
```

**Why:** Source of truth for category placement and rule edges.

**When:** Always — required for `PrismRAG` / `PrismRAGPatch`.

**Mistakes:** Empty `rules` (ingest rejects). Typos in `category_slug` that don’t match a category. Expecting unsupervised discovery of categories.

---

## PrismRAG

**What:** High-level client for ingest, search, communities, bridges, append, quality, export.

**Why:** One object mirroring the former SaaS core RAG surface.

**When:** New apps, demos, Postgres-backed production, GraphRAG-alternative path.

**Mistakes:** Calling `search` before `ingest`. Assuming network license validation (OSS has none).

---

## PrismRAGPatch

**What:** Tier-1 remap helper used with vector DB adapters.

**Why:** Enhance existing stores without moving to full `PrismRAG` graph pipeline.

**When:** You already insert/search in pgvector/Chroma/Pinecone/Weaviate.

**Mistakes:** Expecting communities/bridges from adapters alone.

---

## Dual vectors (semantic + personal)

**What:** Two embeddings per chunk.

**Why:** Preserve content similarity while separating categories in personal space (reduces category bleed).

**When:** Always in full ingest path.

**Mistakes:** Using only deterministic test embeddings in production (pass a real `embed_fn`).

---

## Word graph and rule edges

**What:** Graph linking words/chunks that share a category (plus optional semantic edges during build).

**Why:** Relationship-aware retrieval without a graph DB.

**When:** Domain RAG where same-category chunks should retrieve together.

**Mistakes:** Assuming edges come from document co-occurrence like classic GraphRAG.

---

## Communities

**What:** Louvain clusters over the word graph (`[graph]` extra).

**Why:** Route search and label topic groups.

**When:** After ingest with enough rules/records to form clusters.

**Mistakes:** Expecting many communities on tiny mappings.

---

## Graph RAG search vs direct

**What:** `search()` returns `retrieval_mode` of `graph_rag`, `direct`, or `empty`.

**Why:** Prefer structure when available; fall back to vectors.

**When:** Default for `PrismRAG.search`.

**Mistakes:** Hard-coding expectations that every query is `graph_rag`.

---

## category_filter

**What:** Optional argument to restrict hits to one `category_slug`.

**Why:** Hard boundary when projection alone is not enough.

**When:** Regulated queries (“only medication”).

**Mistakes:** Filtering a category that has no ingested chunks.

---

## Bridges

**What:** `create_bridge(community_a, community_b)` — synthetic cross-community link.

**Why:** Controlled hops between taxonomy branches.

**When:** Cross-topic questions after you have ≥2 communities.

**Mistakes:** Creating bridges before ingest.

---

## Append and quality

**What:** `append_chunks` adds chunks/rules; `chunk_quality` scores assignments.

**Why:** Grow the KB without full retrain; catch weak placements.

**When:** Production incremental updates.

**Mistakes:** Append without an active mapping (must ingest first).

---

## Stores

| Store | What | When |
|-------|------|------|
| `MemoryStore` | In-process | Tests, notebooks |
| `PostgresStore` | `prismrag.*` tables | Production persistence |

**Mistakes:** Skipping `schema.sql` / `ensure_tenant` for Postgres.

---

## Adapters

**What:** Thin wrappers that remap vectors on insert/search.

**Why:** Use PrismRAG projection without abandoning your DB.

**When:** Existing vector deployments.

**Mistakes:** Confusing adapter remap with full graph RAG feature set.
