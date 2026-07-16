# PrismRAG example — taxonomy Graph RAG replacement

Minimal example that proves **PrismRAG can replace co-occurrence Graph RAG** when you need **controlled connections** between base chunks.

**Mechanism:** you customize a mapping (`word → category`) → same-category words get **rule edges** → dual embeddings (768-d semantic + 256-d personal) → Graph RAG search. Chunks stay separate — no mega-chunk.

## Quick start (PyPI)

```powershell
cd examples\graph-rag-replacement
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python demo_taxonomy_connection.py
pytest test_demo.py -v
```

No database, API key, or license required — `MemoryStore` + offline deterministic embeddings.

## Use local package (develop in this repo)

```powershell
pip install -e "..\..\prismrag_patch[graph]"
python demo_taxonomy_connection.py
pytest test_demo.py -v
```

## What you will see

| Step | What happens |
|------|----------------|
| **1** | Map `volatility` + `drawdown` → `risk` (shared category) |
| **1a** | Dual vectors per chunk: personal **256-d** + semantic **768-d** |
| **1b** | Explicit **rule edge** `volatility <-> drawdown` |
| **1c** | Personal-space cosine higher for same category |
| **1e** | Search *risk metrics* returns **both** risk chunks (still separate) |
| **2** | Contrast: different categories → **no** rule edge |
| **3** | `create_bridge` links risk/growth communities |

## Mapping snippet (the customization lever)

```python
mapping = {
    "categories": [
        {"slug": "risk", "label": "Risk & Compliance"},
        {"slug": "growth", "label": "Growth & Revenue"},
    ],
    "rules": [
        {"word": "volatility", "category_slug": "risk"},
        {"word": "drawdown", "category_slug": "risk"},  # same category -> rule edge
        {"word": "revenue", "category_slug": "growth"},
    ],
}
```

## Honest positioning

| Use PrismRAG when… | Prefer classic auto GraphRAG when… |
|--------------------|-------------------------------------|
| You can define taxonomy / domain rules | You want zero mapping, corpus-only graph |
| Auditability of connections matters | Open-domain co-occurrence is enough |
| Same docs must yield different graphs per client | One statistical graph for everyone |

## Expected output

`demo_taxonomy_connection.py` exits **0** and prints `SUMMARY`.  
`pytest test_demo.py -v` passes.

## Links

- Product INFO: [INFO.md](../../INFO.md)
- Landing: https://www.insightits.com/products/prismrag.html
- PyPI: https://pypi.org/project/prismrag-patch/
