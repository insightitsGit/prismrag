# PrismRAG — Architecture

> **Current product (2026):** pip-only OSS library [`prismrag-patch`](https://pypi.org/project/prismrag-patch/).  
> See [INFO.md](../INFO.md) for landing-page summary. Legacy SaaS diagram below is **archived** (Azure retired).

---

## What problem we solve

Standard Graph RAG derives relationships **from** data — co-occurrence statistics decide which concepts are related. Two clients with the same documents get the same knowledge graph regardless of domain expertise.

PrismRAG reverses the direction. The client defines the mapping first ("these words belong to this category, in my domain"). Data is embedded **into** that mapping's vector space. The knowledge graph reflects the client's expertise, not Wikipedia's.

---

## Library architecture (current)

```
┌─────────────────────────────────────────────────────────────────┐
│  Your application (FastAPI, Django, notebook, agent, ETL job)    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  prismrag_patch.PrismRAG                                        │
│  ingest · search · communities · bridges · append · quality     │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐
│  MemoryStore    │ │  PostgresStore  │ │  Vector DB adapters  │
│  (local/tests)  │ │  prismrag.*     │ │  pgvector/Chroma/…   │
└─────────────────┘ └────────┬────────┘ └──────────────────────┘
                             │
                             ▼
                    PostgreSQL + pgvector
                    (optional self-hosted)
```

### Pipeline modules (library)

| Module | Role |
|--------|------|
| `mapping/rules.py` | Tier-1 category assignment + 768→256 projection |
| `pipeline/ingest.py` | Inline ingest → graph → communities |
| `graph/builder.py` | Rule + semantic edges |
| `graph/community.py` | Louvain + labels |
| `retrieval/search.py` | Graph RAG + direct fallback |
| `retrieval/bridge.py` | Bridge vectors |
| `pipeline/append.py` | Incremental chunks |
| `pipeline/quality.py` | Chunk quality scores |
| `store/postgres.py` | SaaS schema parity |

---

## Data flow: Ingest (library)

```
Client mapping JSON { categories, rules }
  +
Inline records [{ word, text, category_hint? }]
  │
  ▼
RulesStrategy.assign_batch  → 768-d sem + 256-d personal per chunk
  │
  ▼
Store.upsert_chunk  → chunk_embedding (Postgres) or MemoryStore
  │
  ▼
build_graph  → rule edges (same category) + semantic edges (cosine ≥ 0.70)
  │
  ▼
build_communities  → Louvain → community_summary + community_member
```

---

## Data flow: Search (library)

```
Query string
  │
  ▼
embed_fn(query tokens) → 768-d query vector
  │
  ▼
Rank communities by centroid cosine
  │
  ▼
Seed words (top community words + query tokens) → BFS on word_graph_edge
  │
  ▼
Fetch candidate chunks → semantic re-rank → hits
  │
  ▼
(fallback) Direct cosine on sem_embedding if no communities
```

---

## Legacy: SaaS architecture (archived)

The former Azure deployment (Container Apps, worker, Service Bus, Stripe billing) is documented in [deployment.md](deployment.md) and the diagram in git history. Resource group `prismrag-rg` was deleted for zero cost. Source code remains under `prismrag/` for self-host reference.

---

## Database schema

See `prismrag/schema.sql`. Key tables: `mapping_version`, `mapping_rule`, `chunk_embedding`, `word_graph_edge`, `community_summary`, `bridge_vector`, `ingest_job`.

PostgresStore in the library reads/writes these tables directly — no HTTP API required.

---

## Further reading

- [INFO.md](../INFO.md) — product overview for landing page
- [technical.md](technical.md) — vectors, graph, retrieval math
- [prismrag_patch/README.md](../prismrag_patch/README.md) — install + API matrix
