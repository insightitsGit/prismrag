# Comparison

Factual positioning. PrismRAG does not claim to dominate every RAG stack.

## Summary

| Need | Prefer |
|------|--------|
| Taxonomy / audit / multi-tenant category graphs | **PrismRAG** |
| Unsupervised entity-relation discovery from corpus | Classic GraphRAG-style pipelines |
| Agent workflows / state machines | LangGraph (call PrismRAG from tools) |
| Orchestration only | LangChain / LlamaIndex (+ PrismRAG as retriever) |
| Pure vector search | Your vector DB alone |

---

## Comparison table

| Dimension | PrismRAG | Co-occurrence / auto GraphRAG | LangChain / LlamaIndex | LangGraph | Plain vector DB |
|-----------|----------|-------------------------------|------------------------|-----------|-----------------|
| Primary job | Taxonomy-grounded retrieval | Corpus graph + retrieve | Orchestrate RAG apps | Agent workflows | Store & ANN search |
| Graph source | Your mapping rules | Docs / extraction | N/A (pluggable) | N/A | None |
| Requires graph DB | No | Often yes | No | No | No |
| Category audit trail | Yes (`category_slug` / rules) | Usually weak | Depends on custom code | N/A | No |
| Replaces vector DB | No — integrates | Sometimes hybrid | No | No | — |
| Replaces agent framework | No | No | Partial overlap with LC | — | No |
| Install model | `pip install prismrag-patch` | Varies (often heavier) | pip | pip | Vendor / self-host |
| License (this package) | Apache-2.0 | Varies | Varies | Varies | Varies |

---

## “Can it replace X?”

| X | Answer |
|---|--------|
| Traditional GraphRAG | **Often for domain/taxonomy use cases.** Not when you need unsupervised corpus knowledge graphs. |
| LangGraph | **No.** Different layer. |
| LangChain | **No.** Complementary. |
| Neo4j | **Not as a general graph DB.** Avoids needing one for PrismRAG’s design. |
| OpenAI embeddings | **No.** BYO `embed_fn`. |
| Pinecone/Weaviate/pgvector | **No.** Integrate via adapters or PostgresStore. |

---

## Honest differentiators

1. Mapping-first (you define categories).  
2. Dual vectors + rule edges without mandatory graph DB.  
3. Explicit `category_slug` on results.  
4. Remap adapters for existing stores.  

## Honest non-goals

1. Unsupervised GraphRAG discovery.  
2. Agent orchestration.  
3. Hosted multi-tenant SaaS (library is primary; `prismrag/` is archived).  
4. First-class Supports/Contradicts edge-type API (encode via categories today).
