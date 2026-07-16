# Architecture

## Where PrismRAG sits in a production stack

```
┌────────────────────────────────────────────┐
│  App / agents / LangChain / custom API     │
└─────────────────────┬──────────────────────┘
                      │ queries + context
                      ▼
┌────────────────────────────────────────────┐
│  PrismRAG (prismrag_patch)                 │
│  mapping → ingest/search → explainable hits│
└─────────────────────┬──────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
  MemoryStore   PostgresStore   Vector adapters
  (dev/test)    (prismrag.*)    (pgvector/Chroma/
                                 Pinecone/Weaviate)
```

PrismRAG is a **retrieval layer**. It is not the LLM, not the agent runtime, and not a replacement for your vector database vendor.

## Data flow (full client)

```
mapping (categories + rules)
        │
        ▼
ingest(records)
        │
        ├─ RulesStrategy: assign category
        ├─ embed → semantic + personal vectors
        ├─ persist chunks
        ├─ build word graph (rule edges)
        └─ Louvain communities
        │
        ▼
search(query)
        │
        ├─ try graph_rag (communities → BFS → re-rank)
        └─ else direct semantic
        │
        ▼
results[{category_slug, chunk_ref, chunk_text, score, ...}]
```

## Two integration shapes

### A. Full pipeline (`PrismRAG`)

Use when you want ingest + graph search + communities + bridges in one client.

- Dev: default `MemoryStore`  
- Prod: `PrismRAG.from_postgres(dsn, mapping, tenant_id)` after applying `prismrag/schema.sql`

### B. Remap-only (`PrismRAGPatch` + adapter)

Use when chunks already live in your vector DB and you only need Tier-1 category projection on insert/search.

Adapters do **not** automatically give you Louvain communities / full graph RAG unless you also run the full client or store that data yourself.

## Dual vectors

| Vector | Typical dim | Role |
|--------|-------------|------|
| Semantic | 768 (or model) | Content similarity, re-rank |
| Personal | 256 | Category-grounded space |

## What this architecture intentionally excludes

- Hosted SaaS dependency (legacy `prismrag/` API is archived)  
- Mandatory graph database (Neo4j, etc.)  
- Built-in embedding SaaS lock-in (BYO `embed_fn`)  
- Agent workflow engine  

## Legacy note

Older docs under `docs/ARCHITECTURE.md` / `DOC/` may describe Azure SaaS. Treat the **pip library** path above as current.
