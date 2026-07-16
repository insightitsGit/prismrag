# Taxonomy Scorecard

Standard Graph RAG builds edges from document co-occurrence — same PDFs, same graph
for everyone. PrismRAG inverts that: **you** define categories + word→category rules;
same-category words get **rule edges**; dual embeddings (768-d semantic + 256-d personal)
power Graph RAG search. Chunks stay separate — no mega-chunk.

This page is the **self-serve scorecard**: run the taxonomy connection demo, see the
rule edge + dual retrieve, optionally reply **TAXONOMY** for a free one-page mapping
connection map. **No call required.**

## 30-second path (local demo)

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

Exit code **0** + `SUMMARY`. Optional: `pytest test_demo.py -v` (3 tests).

## One-liner install check

```bash
pip install "prismrag-patch[graph]==0.2.1"
python -c "from prismrag_patch import PrismRAG; print('ok', PrismRAG)"
```

## What this proves (honest)

| Claim | Evidence in demo |
|-------|------------------|
| Graph RAG replacement for *controlled* connections | Shared category → rule edge → graph retrieve |
| Customization is the lever | You own the mapping JSON |
| Not a mega-chunk merge | Chunks remain separate with dual embeddings |
| When classic GraphRAG wins | Zero-taxonomy / fully auto corpus graph |

## Soft CTA — Taxonomy map (async, free)

Reply **TAXONOMY** (GitHub issue comment, X/LI DM, or email prismrag@insightits.com) with:

- your draft `categories` + `rules` JSON (redact secrets), **or**
- the `SUMMARY` / pytest output from this demo

You get a **one-page mapping connection map within 48h**. Still no calendar.

## What this is not

- Not PrismGuard (injection firewall — different CTA: GRADE)
- Not ChorusGraph (agent runtime — different CTA: LEDGER)
- Not a cold Calendly ask
- Not “auto GraphRAG with zero mapping work”

## Links

- PyPI: https://pypi.org/project/prismrag-patch/
- GitHub: https://github.com/insightitsGit/prismrag
- Example: https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement
- Website: https://www.insightits.com/products/prismrag.html
- Product INFO: [INFO.md](../INFO.md)
- Runnable example: [examples/graph-rag-replacement](../examples/graph-rag-replacement/)
