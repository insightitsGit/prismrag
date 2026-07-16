# PrismRAG example — you don’t need a separate Graph RAG stack

This is the **smoke demo** for PrismRAG.

**Live on GitHub:** https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement  

It proves **PrismRAG replaces co-occurrence Graph RAG** for connecting base chunks. You do **not** need to bolt on a separate Graph RAG library beside it. PrismRAG already ships the Graph RAG job — with a graph **you** define via taxonomy (categories + rules), not a graph guessed from co-occurrence.

**Also read:** [Taxonomy Scorecard](../../docs/taxonomy-scorecard.md) · https://github.com/insightitsGit/prismrag/blob/main/docs/taxonomy-scorecard.md

**Mechanism:** mapping (`word → category`) → **rule edges** → dual embeddings (768-d semantic + 256-d personal) → Graph RAG search. Chunks stay separate — no mega-chunk.

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

**SUMMARY line you should see:** *You do NOT need a separate Graph RAG library beside PrismRAG.*

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

## Positioning

| With PrismRAG | Without it (classic Graph RAG) |
|---------------|--------------------------------|
| One pip library: taxonomy → rule edges → graph retrieve | Separate Graph RAG stack + co-occurrence graph |
| You own which chunks connect | Corpus statistics decide the graph |
| Same docs → different graphs per client mapping | Same docs → same graph for everyone |

**Only edge case for classic auto GraphRAG:** you refuse any mapping and want a fully unsupervised corpus graph. Domain / regulated RAG usually wants the PrismRAG path.

## Expected output

`demo_taxonomy_connection.py` exits **0** and prints `SUMMARY`.  
`pytest test_demo.py -v` passes.

## Links

- **This smoke demo (GitHub):** https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement
- **Taxonomy Scorecard:** https://github.com/insightitsGit/prismrag/blob/main/docs/taxonomy-scorecard.md
- Product INFO: [INFO.md](../../INFO.md)
- Landing: https://www.insightits.com/products/prismrag.html
- PyPI: https://pypi.org/project/prismrag-patch/
