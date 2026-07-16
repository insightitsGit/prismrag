# Taxonomy Scorecard

**You don’t need a separate Graph RAG stack.**

Standard Graph RAG builds edges from document co-occurrence — same PDFs, same graph
for everyone. PrismRAG *is* the Graph RAG layer: **you** define categories + word→category
rules; same-category words get **rule edges**; dual embeddings (768-d semantic + 256-d
personal) power Graph RAG search. Chunks stay separate — no mega-chunk.

This page is the **self-serve scorecard**: run the smoke demo, see the rule edge + dual
retrieve, optionally reply **TAXONOMY** for a free one-page mapping connection map.
**No call required.**

## Smoke demo (run this)

**Interactive browser demo (like PrismGuard):**  
https://insightitsgit.github.io/prismrag/demo.html · [`demo.html`](demo.html)

**Folder (CLI):** [`examples/graph-rag-replacement/`](../examples/graph-rag-replacement/)  
**Script:** [`demo_taxonomy_connection.py`](../examples/graph-rag-replacement/demo_taxonomy_connection.py)  
**GitHub:** https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement

```bash
pip install "prismrag-patch[graph]>=0.2.1"
git clone https://github.com/insightitsGit/prismrag.git
cd prismrag/examples/graph-rag-replacement
pip install -r requirements.txt
python demo_taxonomy_connection.py
```

You should see:

1. Dual vectors per chunk — personal **256-d** + semantic **768-d**
2. Explicit **rule edge** `volatility <-> drawdown` (shared `risk` category)
3. Search *risk metrics* returns **both** risk chunks (still separate)
4. Contrast: split categories → **no** rule edge
5. Optional `create_bridge` between communities
6. **SUMMARY:** *You do NOT need a separate Graph RAG library beside PrismRAG.*

Exit code **0**. Optional: `pytest test_demo.py -v` (3 tests).

## One-liner install check

```bash
pip install "prismrag-patch[graph]==0.2.1"
python -c "from prismrag_patch import PrismRAG; print('ok', PrismRAG)"
```

## What this proves (honest)

| Claim | Evidence in smoke demo |
|-------|------------------------|
| No separate Graph RAG product required | PrismRAG does rule edges + communities + graph retrieve |
| Controlled connections via your mapping | Shared category → rule edge → dual retrieve |
| Not a mega-chunk merge | Chunks remain separate with dual embeddings |
| Narrow caveat | Zero mapping / fully unsupervised corpus graph only |

## Soft CTA — Taxonomy map (async, free)

Reply **TAXONOMY** (GitHub issue comment, X/LI DM, or email prismrag@insightits.com) with:

- your draft `categories` + `rules` JSON (redact secrets), **or**
- the `SUMMARY` / pytest output from the smoke demo

You get a **one-page mapping connection map within 48h**. Still no calendar.

## What this is not

- Not PrismGuard (injection firewall — different CTA: GRADE)
- Not ChorusGraph (agent runtime — different CTA: LEDGER)
- Not a cold Calendly ask
- Not “auto GraphRAG with zero mapping work”

## Links

- **Smoke demo:** https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement
- **This scorecard:** https://github.com/insightitsGit/prismrag/blob/main/docs/taxonomy-scorecard.md
- PyPI: https://pypi.org/project/prismrag-patch/
- GitHub: https://github.com/insightitsGit/prismrag
- Website: https://www.insightits.com/products/prismrag.html
- Product INFO: [INFO.md](../INFO.md)
