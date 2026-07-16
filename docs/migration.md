# Migration

## From plain vector RAG (similarity only)

**Before**

```python
# Pseudocode — typical vector search
results = vector_db.query(embed(query), top_k=5)
```

**After (full PrismRAG)**

```python
from prismrag_patch import PrismRAG

rag = PrismRAG(mapping=your_mapping, tenant_id="prod", embed_fn=your_embed)
rag.ingest(records=your_records)  # or continuous append
results = rag.search(query, top_k=5, category_filter=None)
```

**After (keep your DB, remap only)**

```python
from prismrag_patch import PrismRAGPatch
from prismrag_patch.adapters.pgvector import PgvectorAdapter

patch = PrismRAGPatch(mapping=your_mapping)
adapter = PgvectorAdapter(patch, connection=conn)
adapter.insert(text=doc, vector=embed(doc))
hits = adapter.search(query, query_vector=embed(query))
```

**What you keep:** embedding model, app/agent layer, often the same DB.  
**What you add:** a mapping file/table and PrismRAG (or adapter) in the write/read path.

---

## From traditional / co-occurrence GraphRAG

**Typical before**

- Chunk + embed into vector DB  
- Extract entities/relations → load Neo4j or similar  
- Hybrid graph + vector retrieve  

**After with PrismRAG (domain / multi-tenant case)**

1. Encode domain structure as **categories + rules** (your mapping).  
2. `ingest` — builds word graph from rules, not co-occurrence.  
3. `search` — graph_rag / direct without operating a graph DB.  
4. Use `category_filter` / `category_slug` for audit.  

**When this migration is a good fit:** you can define a taxonomy; you need per-tenant graphs; you want less ops.  

**When to keep classic GraphRAG:** you need unsupervised discovery of entities/relations from raw corpus with no mapping.

---

## From LangChain / LlamaIndex retrievers

Keep the framework. Replace the retriever body:

```python
# Pseudocode
def retrieve(query: str):
    out = rag.search(query, top_k=5)
    return [
        {"page_content": h["chunk_text"], "metadata": {"category": h["category_slug"], "ref": h["chunk_ref"]}}
        for h in out["results"]
    ]
```

PrismRAG does **not** replace chains, tools, or memory modules.

---

## From LangGraph (and similar agent runtimes)

**Do not migrate “off LangGraph onto PrismRAG.”** Different layers.

Pattern: LangGraph (or other) node/tool calls `rag.search(...)` and passes hits into the LLM.

---

## Checklist

- [ ] Write or export mapping JSON / DB table  
- [ ] Choose MemoryStore vs PostgresStore vs adapters  
- [ ] Wire `embed_fn` for production  
- [ ] Install `"prismrag-patch[graph]"` if you need communities / graph_rag  
- [ ] Apply `prismrag/schema.sql` if using PostgresStore  
- [ ] Re-ingest or backfill remap for existing vectors  
- [ ] Add `category_filter` where product requires hard isolation  

See also: [examples.md](examples.md), [comparison.md](comparison.md).
