# AI / LLM context — PrismRAG

> Concise reference for humans and coding assistants (Cursor, Copilot, Claude, ChatGPT, Windsurf, Gemini).  
> Do not invent APIs beyond this file and `prismrag_patch/`. Package: **`prismrag-patch` 0.2.1**, import **`prismrag_patch`**.

---

## 10-sentence project summary

1. PrismRAG is an Apache-2.0 Python library (`pip install prismrag-patch`) for taxonomy-grounded RAG retrieval.  
2. You supply a mapping of categories and word→category rules; the library assigns categories and builds retrieval from that mapping.  
3. Each chunk stores dual vectors: ~768-d semantic and ~256-d category-grounded (“personal”) projection.  
4. Ingest builds a word graph (same-category rule edges) and Louvain communities for graph-aware search.  
5. `search()` uses graph RAG routing when possible (`retrieval_mode: graph_rag`) or direct semantic fallback.  
6. Results include `category_slug` so retrieval is auditable against your rules.  
7. Optional `category_filter` hard-limits results to one taxonomy branch.  
8. Persistence: in-memory `MemoryStore`, production `PostgresStore` (`prismrag.*` schema), or Tier-1 adapters for pgvector/Chroma/Pinecone/Weaviate.  
9. It is an alternative approach to co-occurrence GraphRAG and a complement to LangChain/LlamaIndex — not a LangGraph replacement.  
10. Limitations: requires a mapping; no unsupervised corpus graph; no built-in typed edge enums like Supports/Contradicts; BYO embeddings for production quality.

---

## Core concepts

| Term | Definition |
|------|------------|
| **Mapping** | `{"categories": [{"slug","label"}], "rules": [{"word","category_slug"}]}` |
| **Tier-1 / RulesStrategy** | Deterministic word→category assignment + vector projection |
| **Personal vector** | 256-d category-grounded embedding |
| **Semantic vector** | 768-d (or model dim) content embedding |
| **Rule edge** | Graph link between words/chunks sharing a category |
| **Community** | Louvain cluster of related words |
| **Bridge** | Synthetic connector between two communities |
| **PrismRAG** | Full pipeline client |
| **PrismRAGPatch** | Remap-only helper for vector DB adapters |

---

## Key APIs

```python
from prismrag_patch import PrismRAG, PrismRAGPatch, MemoryStore, PostgresStore

rag = PrismRAG(mapping=mapping, tenant_id="...", embed_fn=optional, store=optional)
rag = PrismRAG.from_postgres(dsn, mapping, tenant_id)

rag.ingest(records=[{"word": "...", "text": "..."}])
rag.get_job(job_id)
rag.search(query, top_k=5, category_filter=None)  # → {results, retrieval_mode, ...}
rag.list_communities()
rag.create_bridge(community_a, community_b, bridge_label=None)
rag.append_chunks(chunks=[{"ref","text"}], new_rules=[{"word","category_slug"}])
rag.chunk_quality()
rag.export_chunks()

patch = PrismRAGPatch(mapping=mapping)  # no license key in OSS
patch.remap_vector(vector, text=...)
patch.category_for(text)
```

Adapters (optional extras): `prismrag_patch.adapters.pgvector|chroma|pinecone|weaviate`.

---

## Common use cases

1. Stop category bleed in domain RAG (healthcare, finance, legal).  
2. Multi-tenant / white-label KB: same docs, different mappings.  
3. Relationship-aware retrieval without a graph database (GraphRAG alternative).  
4. Remap-only enhancement of an existing vector table via adapters.  
5. Incremental KB updates with append + quality scoring.

---

## Migration guidance (one paragraph)

From **vector-only RAG**: keep your embedder and store; add a mapping; either run full `PrismRAG.ingest/search` or wrap inserts/queries with `PrismRAGPatch` + adapter. From **co-occurrence GraphRAG**: drop the graph DB / extraction pipeline for domain use cases; encode connections as shared categories and rules; use `search()` for graph_rag mode. From **LangChain/LlamaIndex**: keep the orchestrator; replace or wrap the retriever with PrismRAG search results. Do not replace LangGraph with PrismRAG — use PrismRAG inside tools.

Details: [migration.md](migration.md)

---

## Limitations

- Requires at least one mapping rule for ingest.  
- Deterministic hash embeddings are for offline tests — use a real `embed_fn` in production.  
- GraphRAG path needs the `[graph]` extra (networkx, python-louvain).  
- Adapters provide Tier-1 remap, not the full graph pipeline unless you also use PrismRAG/PostgresStore.  
- Legacy SaaS in `prismrag/` is archived reference — not required for the library.  
- Published OSS build has no license server / no paid license key.

---

## Frequently compared projects

| Project | Relation to PrismRAG |
|---------|----------------------|
| Traditional / Microsoft GraphRAG style | Alternative: auto/co-occurrence graphs vs taxonomy-first |
| LangChain / LlamaIndex | Complementary orchestrators |
| LangGraph | Not a replacement — different layer (agents vs retrieval) |
| Neo4j + RAG | PrismRAG avoids requiring a graph DB for this product’s design |
| Plain pgvector / Chroma | Integrate via adapters or PostgresStore; PrismRAG adds taxonomy |
| Pinecone / Weaviate | Adapter remap path |

Full table: [comparison.md](comparison.md)

---

## Repo pointers

| Path | Role |
|------|------|
| `prismrag_patch/` | Published package source |
| `examples/graph-rag-replacement/` | Taxonomy / GraphRAG-alternative smoke |
| `examples/demo_app/` | PyPI install verification |
| `prismrag/schema.sql` | Postgres schema for PostgresStore |
| `INFO.md` | Product + benchmark notes |
| `tests/test_lib_step*.py` | Library parity tests |
