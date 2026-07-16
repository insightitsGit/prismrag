# Examples

Practical patterns. Full runnable demos: `examples/graph-rag-replacement/`, `examples/demo_app/`.

---

## 1. Domain RAG with hard category boundaries

**Business problem:** A medical assistant must not mix medication guidance with lab-result snippets.

```python
from prismrag_patch import PrismRAG

mapping = {
    "categories": [
        {"slug": "medication", "label": "Medication"},
        {"slug": "lab_results", "label": "Lab Results"},
    ],
    "rules": [
        {"word": "metformin", "category_slug": "medication"},
        {"word": "insulin", "category_slug": "medication"},
        {"word": "troponin", "category_slug": "lab_results"},
        {"word": "hba1c", "category_slug": "lab_results"},
    ],
}

rag = PrismRAG(mapping=mapping, tenant_id="clinic-a")
rag.ingest(records=[
    {"word": "metformin", "text": "Metformin dosing for type 2 diabetes."},
    {"word": "troponin", "text": "Elevated troponin suggests myocardial injury."},
])

meds = rag.search("diabetes treatment", top_k=5, category_filter="medication")
```

**Why not similarity alone:** embeddings often place clinical terms near each other across categories.

---

## 2. Multi-tenant knowledge (same docs, different mappings)

**Business problem:** Two clients share a document dump but need different category models.

```python
rag_a = PrismRAG(mapping=client_a_mapping, tenant_id="tenant-a")
rag_b = PrismRAG(mapping=client_b_mapping, tenant_id="tenant-b")
# ingest same records into each — graphs differ by mapping
```

---

## 3. GraphRAG-style retrieval without a graph database

**Business problem:** Risk metrics should retrieve together; growth metrics should not bleed in.

```python
# mapping puts volatility + drawdown under "risk"
rag.ingest(records=[...])
out = rag.search("What are the risk metrics?", top_k=5)
assert out["retrieval_mode"] in ("graph_rag", "direct")
```

Smoke demo: `examples/graph-rag-replacement/demo_taxonomy_connection.py`.

---

## 4. Enhance an existing pgvector table (remap only)

**Business problem:** You already store embeddings; you want category nudge on write/read.

```python
from prismrag_patch import PrismRAGPatch
from prismrag_patch.adapters.pgvector import PgvectorAdapter

patch = PrismRAGPatch(mapping=mapping)
adapter = PgvectorAdapter(patch, connection=conn)
adapter.insert(text=doc, vector=embed(doc))
```

---

## 5. Incremental production updates

**Business problem:** Add vocabulary without full re-index.

```python
rag.append_chunks(
    chunks=[{"ref": "nausea", "text": "Patient reports nausea after dose."}],
    new_rules=[{"word": "nausea", "category_slug": "symptoms"}],
)
print(rag.chunk_quality()["summary"])
```

---

## 6. Export for downstream agents

```python
for c in rag.export_chunks():
    # c["embedding"], c["sem_embedding"], c["category_slug"]
    ...
```

---

## Try locally

```bash
pip install "prismrag-patch[graph]"
cd examples/demo_app && pip install -r requirements.txt && python run_verification.py
```
