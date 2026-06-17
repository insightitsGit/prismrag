# PrismRAG — Architecture

## What problem we solve

Standard Graph RAG derives relationships **from** data — co-occurrence statistics decide which concepts are related. This means two clients with the same documents get the same knowledge graph regardless of their domain expertise.

PrismRAG reverses the direction. The client defines the mapping first ("these words belong to this category, in my domain"). Data is then embedded **into** that mapping's vector space. The knowledge graph reflects the client's expertise, not Wikipedia's.

---

## System overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Clients                                                                    │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────────────────┐  │
│  │  Web UI  │  │  REST API    │  │  MCP (AI agents: Claude, GPT, etc.) │  │
│  │dashboard │  │  (JWT/APIkey)│  │  stdio or HTTP transport            │  │
│  └────┬─────┘  └──────┬───────┘  └──────────────┬──────────────────────┘  │
└───────┼───────────────┼──────────────────────────┼──────────────────────── ┘
        │               │                          │
        ▼               ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Azure Container Apps — API service (FastAPI, min=1 replica)                │
│                                                                              │
│  Middleware stack (outermost → innermost):                                   │
│    CORS → AuditMiddleware (log every call) → Router                         │
│                                                                              │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ /api/auth    │ │ /api/billing│ │ /api/prismrag│ │ /api/prismrag/     │  │
│  │ register     │ │ checkout    │ │ jobs         │ │ upload/presign     │  │
│  │ login        │ │ portal      │ │ search       │ │ upload/confirm     │  │
│  │ me           │ │ webhook     │ │ bridge       │ │                    │  │
│  │ api-keys     │ │ plans       │ │ tenants      │ │                    │  │
│  └──────────────┘ └─────────────┘ └──────┬───────┘ └────────────────────┘  │
└─────────────────────────────────────────┬┼──────────────────────────────────┘
                                          ││
                          small jobs      ││      large jobs (>1 MB)
                          (inline)        ││      via Azure Blob + Service Bus
                                          ▼▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Azure Container Apps — Worker service (min=0, scale on queue depth)        │
│                                                                              │
│  Ingest pipeline:                                                            │
│    Source adapter → Gemini embed → Mapping strategy → Write chunks          │
│    → Build graph edges → Louvain communities → Label via Gemini             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                ┌────────────────┴────────────────┐
                ▼                                 ▼
┌───────────────────────────┐    ┌────────────────────────────────────────────┐
│  PostgreSQL + pgvector    │    │  Azure Blob Storage                        │
│  (Neon Phase 1,           │    │  Large file staging                        │
│   Azure Flexible Phase 2+)│    │  Files deleted after processing            │
│                           │    └────────────────────────────────────────────┘
│  Schema: prismrag.*       │
│  · tenant                 │    ┌────────────────────────────────────────────┐
│  · mapping_version        │    │  Azure Service Bus                         │
│  · mapping_rule           │    │  Queue: prismrag-jobs                      │
│  · chunk_embedding        │    │  Worker scales on message count            │
│  · word_graph_edge        │    └────────────────────────────────────────────┘
│  · community_summary      │
│  · bridge_vector          │    ┌────────────────────────────────────────────┐
│  · api_request_log        │    │  Azure Cache for Redis (Phase 3)           │
│  · search_result_log      │    │  Rate-limit sliding windows                │
│  · user_account           │    │  Monthly quota counters                    │
│  · api_key                │    │  Falls back to Postgres if absent          │
│  · usage_event            │    └────────────────────────────────────────────┘
└───────────────────────────┘
```

---

## Data flow: Ingest

```
Client input (CSV / Excel / SQL / API / existing chunk store)
  │
  ▼
Source Adapter          streams Record(word, text, category_hint, metadata)
  │
  ▼
Gemini embed_texts()    768-d semantic embedding, DB-cached
  │
  ▼
Mapping Strategy
  ├── Tier 1 (RulesStrategy)
  │     word → explicit category lookup (mapping_rule table)
  │     deterministic QR projection 768→256-d
  │     30% category one-hot + 70% semantic content
  │     L2 normalize
  │
  └── Tier 2 (MLPStrategy)
        trains 3-layer PyTorch MLP on Tier-1 pairs
        768 → 512 → 512 → 256-d L2-norm
        InfoNCE loss (τ=0.20) + anchor repulsion (weight=0.35)
        falls back to Tier-1 if torch unavailable
  │
  ▼
chunk_embedding table   VECTOR(256) personal + VECTOR(768) semantic
  │
  ▼
Graph builder           rule edges (same category) + semantic edges (cosine ≥ 0.70)
  │
  ▼
Louvain community       python-louvain, parallel Gemini labeling
  │
  ▼
community_summary       centroid VECTOR(768), HNSW indexed
```

## Data flow: Search (Graph RAG retrieval)

```
Query text
  │
  ▼
Gemini embed            768-d query vector
  │
  ▼
Community ranking       pgvector HNSW cosine search on community centroids
  │
  ▼
BFS 2-hop expand        word_graph_edge traversal (rule + semantic + bridge edges)
  │
  ▼
Chunk fetch             chunk_embedding rows for expanded word set
  │
  ▼
MLP re-rank (Tier 2)    cosine similarity in 256-d personal space
  │  or
  └─ Semantic re-rank (Tier 1)   cosine in 768-d Gemini space
  │
  ▼
Direct HNSW fallback    if graph is empty (new tenant with no communities yet)
  │
  ▼
SearchResponse          top_k hits with score, word, category, community label
```

---

## Multi-tenancy

Every row in every table is scoped by `tenant_id` (UUID). A tenant is a workspace owned by one user account. Plan quotas control how many tenants a user can create.

There is no cross-tenant data leak possible at the SQL level — all queries include `WHERE tenant_id = %s` with the authenticated user's tenant.

---

## Scaling model

| Traffic level | Bottleneck | Action |
|---|---|---|
| 0–100 rps | None | Default config |
| 100–500 rps | API replicas | Container Apps HTTP scaling (auto) |
| 500–2000 rps | DB connections | Increase pool size, add PgBouncer |
| 2000+ rps | Postgres reads | Add read replica, point search queries there |
| Any ingest burst | Worker capacity | Service Bus queue → worker auto-scales to 10 replicas |

---

## Security boundaries

- All secrets in Azure Key Vault / Container Apps secrets — never in code or image
- DB accessible only via private endpoint (Phase 2+) — not reachable from public internet
- API keys stored as SHA-256 hash only — raw key shown once, never stored
- Passwords: bcrypt (PBKDF2 fallback if bcrypt unavailable)
- JWT: 72-hour expiry, HS256, secret rotatable without code deploy
- Request bodies sanitized before audit log write (passwords, keys replaced with `***`)
- Response bodies suppressed in audit log for auth endpoints
- File uploads bypass API server entirely (client → Azure Blob via SAS) — no large payloads in memory
