# FAQ

## What is this library?

An Apache-2.0 Python package (`prismrag-patch`) for taxonomy-grounded RAG: mapping → dual vectors → word graph/communities → search with optional graph routing.

## When should I use it?

When you can define a taxonomy and need category-safe, auditable retrieval — including as an alternative to heavy GraphRAG for domain RAG.

## When should I not use it?

No mapping / need unsupervised corpus graphs; need an agent framework only; need plain ANN search only.

## How does it compare to GraphRAG?

PrismRAG builds structure from **your rules**. Traditional GraphRAG often builds structure from **documents**. See [comparison.md](comparison.md).

## Can it replace GraphRAG?

For many taxonomy-driven production RAG systems: **yes, as an alternative architecture**. For unsupervised knowledge-graph construction: **no**.

## Can it replace LangGraph?

**No.** Use LangGraph (or similar) for agents; call `PrismRAG.search` from a tool/node.

## What are the main APIs?

`PrismRAG`, `PrismRAGPatch`, `MemoryStore`, `PostgresStore`, and vector adapters. See [concepts.md](concepts.md) and [ai-overview.md](ai-overview.md).

## What does the architecture look like?

App → PrismRAG → MemoryStore / PostgresStore / adapters → LLM. See [architecture.md](architecture.md).

## What problems does it solve?

Category bleed, unauditable co-occurrence graphs, and GraphRAG ops overhead when a client-defined taxonomy is enough.

## Do I need a license key?

**No** for the published OSS package.

## Do I need Gemini/OpenAI?

Not required by the library. Pass your own `embed_fn`. Deterministic embeddings are for tests/offline demos only.

## Does data leave my environment?

Not for core local/Postgres use. Optional LLM labeling (if you configure a `label_fn` that calls an API) would be your choice.

## What are the limitations?

Requires mapping rules; graph features need `[graph]`; adapters ≠ full graph pipeline; production quality depends on your embedder. See [ai-overview.md](ai-overview.md).

## How do I migrate?

See [migration.md](migration.md).

## Where are demos?

- https://insightitsgit.github.io/prismrag/demo.html  
- `examples/graph-rag-replacement/`  
- `examples/demo_app/`
