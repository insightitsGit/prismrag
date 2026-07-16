# Overview

## What is PrismRAG?

PrismRAG is an open-source Python library for **taxonomy-grounded retrieval**.

You define categories and word→category rules. The library maps chunks into that taxonomy, stores dual embeddings, builds a word graph from your rules, and searches with optional graph-aware routing.

Published as **`prismrag-patch`** on PyPI. Import as **`prismrag_patch`**.

## Who is it for?

| Audience | Need |
|----------|------|
| Backend / ML engineers | Category-safe RAG without a second GraphRAG stack |
| Platform teams | Multi-tenant retrieval with per-tenant mappings |
| Regulated domains | Auditable rule → chunk → hit trail |
| Agent builders | Better context for tools (still use LangGraph/etc. for orchestration) |

## What problem does it solve?

1. **Category bleed** — similarity returns wrong-domain chunks.  
2. **Unauditable graphs** — co-occurrence GraphRAG edges you did not define.  
3. **Ops-heavy GraphRAG** — graph DB + extraction + multi-service deploy for domain RAG that a mapping could solve.

## Why use it instead of existing solutions?

| If you currently… | PrismRAG offers… |
|-------------------|------------------|
| Vector similarity only | Category projection + optional `category_filter` |
| Auto / co-occurrence GraphRAG | Graph built from **your** rules |
| LangChain retriever | Drop-in retrieval results (orchestrator stays) |
| Separate Neo4j for domain links | In-process word graph / Postgres — no Neo4j required for this design |

## Positioning (explicit)

- **Alternative to:** traditional co-occurrence GraphRAG pipelines (for taxonomy-driven domains)  
- **Complements:** LangChain, LlamaIndex, custom FastAPI RAG services  
- **Does not replace:** LangGraph, AutoGen, CrewAI, embedding models, vector databases  

## Capabilities that ship today

Documented in code (`prismrag_patch/`):

- `PrismRAG` ingest / search / communities / bridges / append / quality / export  
- `PrismRAGPatch` Tier-1 remap  
- `MemoryStore`, `PostgresStore`  
- Adapters: pgvector, Chroma, Pinecone, Weaviate  

## Related docs

- [ai-overview.md](ai-overview.md) — short LLM-oriented summary  
- [architecture.md](architecture.md) · [concepts.md](concepts.md) · [migration.md](migration.md) · [comparison.md](comparison.md) · [faq.md](faq.md)
