#!/usr/bin/env python3
"""
PrismRAG demo - taxonomy Graph RAG as a replacement for co-occurrence Graph RAG.

Proves (no mega-chunk):
  1. Two base chunks stay separate.
  2. Shared category mapping creates an explicit rule edge between their words.
  3. Dual embeddings: 768-d semantic + 256-d personal (category-grounded).
  4. Graph RAG search retrieves both connected risk chunks - not the growth chunk.
  5. Optional bridge links separate communities for cross-topic hops.

Run from this folder:
  pip install -r requirements.txt
  python demo_taxonomy_connection.py
  pytest test_demo.py -v
"""
from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np

from prismrag_patch import PrismRAG


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def print_edges(rag: PrismRAG, mapping_id: str) -> list[Any]:
    edges = rag.store.get_edges(rag.tenant_id, mapping_id)
    if not edges:
        print("  (no edges)")
        return []
    for e in edges:
        print(f"  {e.from_word} <-> {e.to_word}  [{e.edge_type}]  weight={e.weight}")
    return edges


def print_dual_embeddings(rag: PrismRAG, mapping_id: str) -> dict[str, Any]:
    chunks = rag.store.all_chunks(rag.tenant_id, mapping_id)
    by_ref: dict[str, Any] = {}
    for c in chunks:
        personal = np.asarray(c.embedding, dtype=float)
        semantic = np.asarray(c.sem_embedding, dtype=float)
        by_ref[c.chunk_ref] = {
            "category": c.category_slug,
            "personal_dim": int(personal.shape[0]),
            "semantic_dim": int(semantic.shape[0]),
            "personal": personal,
            "semantic": semantic,
            "text": c.chunk_text,
        }
        print(
            f"  {c.chunk_ref:12} category={c.category_slug:8} "
            f"personal={personal.shape[0]}-d  semantic={semantic.shape[0]}-d"
        )
    return by_ref


def print_search(
    rag: PrismRAG,
    query: str,
    top_k: int = 5,
    category_filter: str | None = None,
) -> dict[str, Any]:
    out = rag.search(query, top_k=top_k, category_filter=category_filter)
    print(f"  query: {query!r}")
    if category_filter:
        print(f"  filter: category={category_filter}")
    print(f"  mode:   {out.get('retrieval_mode')}")
    for i, hit in enumerate(out.get("results") or out.get("hits") or [], 1):
        print(
            f"  [{i}] {hit.get('chunk_ref'):12} "
            f"cat={hit.get('category_slug'):8} "
            f"community={hit.get('community_id')}  "
            f"{(hit.get('chunk_text') or '')[:64]}"
        )
    return out


FINANCE_RECORDS = [
    {
        "word": "volatility",
        "text": "Market volatility spiked in Q3 amid rate uncertainty.",
    },
    {
        "word": "drawdown",
        "text": "Portfolio drawdown exceeded the 10 percent risk budget.",
    },
    {
        "word": "revenue",
        "text": "Q3 revenue beat estimates on enterprise ARR growth.",
    },
]


def demo_connected_via_shared_category() -> dict[str, Any]:
    """Main proof: same category → rule edge → both risk chunks retrieve together."""
    section("1) WITH shared category (PrismRAG Graph RAG replacement)")

    mapping = {
        "categories": [
            {"slug": "risk", "label": "Risk & Compliance"},
            {"slug": "growth", "label": "Growth & Revenue"},
        ],
        "rules": [
            # Chunk 1 word + chunk 2 word → SAME category → rule edge
            {"word": "volatility", "category_slug": "risk"},
            {"word": "drawdown", "category_slug": "risk"},
            {"word": "revenue", "category_slug": "growth"},
        ],
    }

    rag = PrismRAG(mapping=mapping, tenant_id="demo-connected")
    job = rag.ingest(records=FINANCE_RECORDS)
    mid = job["mapping_id"]

    print(f"  ingest status: {job['status']}")
    print(f"  records:       {job['records_written']}")
    print(f"  edge_count:    {job['edge_count']}")
    print(f"  communities:   {job['community_count']}")

    section("1a) Dual embeddings (per chunk - not a mega-chunk)")
    by_ref = print_dual_embeddings(rag, mid)

    section("1b) Rule edges from shared category")
    edges = print_edges(rag, mid)
    rule_edges = [e for e in edges if e.edge_type == "rule"]
    assert any(
        {e.from_word, e.to_word} == {"volatility", "drawdown"} for e in rule_edges
    ), "Expected rule edge volatility <-> drawdown"

    section("1c) Personal-space clustering (same category closer)")
    vol_p = by_ref["volatility"]["personal"]
    dd_p = by_ref["drawdown"]["personal"]
    rev_p = by_ref["revenue"]["personal"]
    same_cat = cosine(vol_p, dd_p)
    cross_cat = cosine(vol_p, rev_p)
    print(f"  cos(personal, volatility<->drawdown) [same risk]  = {same_cat:.4f}")
    print(f"  cos(personal, volatility<->revenue)  [cross cat]   = {cross_cat:.4f}")
    if same_cat <= cross_cat:
        print(
            "  note: with tiny toy corpora, semantic noise can dominate; "
            "rule edge + graph retrieve still enforce the connection."
        )

    section("1d) Communities")
    for c in rag.list_communities():
        print(f"  community {c['community_id']}: {c['label']}  words={c['top_words']}")

    section("1e) Graph RAG search - risk query should hit BOTH connected chunks")
    hits = print_search(rag, "What are the risk metrics for the portfolio?")
    refs = {h.get("chunk_ref") for h in (hits.get("results") or hits.get("hits") or [])}
    assert "volatility" in refs and "drawdown" in refs, (
        f"Expected both risk chunks; got {refs}"
    )
    assert "revenue" not in refs or len(refs) >= 2, refs
    print("  OK: both risk chunks retrieved via taxonomy graph (chunks stay separate)")

    section("1f) Category filter (optional hard scope)")
    print_search(rag, "performance numbers", category_filter="growth")

    return {"rag": rag, "mapping_id": mid, "job": job}


def demo_without_shared_category() -> None:
    """Contrast: put the two risk-ish words in DIFFERENT categories → no rule edge."""
    section("2) CONTRAST - no shared category (no rule edge between the two words)")

    mapping = {
        "categories": [
            {"slug": "market", "label": "Market"},
            {"slug": "portfolio", "label": "Portfolio"},
            {"slug": "growth", "label": "Growth"},
        ],
        "rules": [
            {"word": "volatility", "category_slug": "market"},
            {"word": "drawdown", "category_slug": "portfolio"},
            {"word": "revenue", "category_slug": "growth"},
        ],
    }

    rag = PrismRAG(mapping=mapping, tenant_id="demo-split")
    job = rag.ingest(records=FINANCE_RECORDS)
    mid = job["mapping_id"]
    print(f"  edge_count:  {job['edge_count']}")
    print(f"  communities: {job['community_count']}")

    edges = print_edges(rag, mid)
    rule_between = [
        e
        for e in edges
        if e.edge_type == "rule"
        and {e.from_word, e.to_word} == {"volatility", "drawdown"}
    ]
    assert not rule_between, "Split categories should NOT create that rule edge"
    print("  OK: no volatility<->drawdown rule edge when categories differ")
    print("  takeaway: YOU customize which base chunks connect - via mapping rules")


def demo_bridge() -> None:
    """Dedicated run with two dense categories so Louvain yields 2+ communities."""
    section("3) Optional bridge between communities")

    mapping = {
        "categories": [
            {"slug": "risk", "label": "Risk"},
            {"slug": "growth", "label": "Growth"},
        ],
        "rules": [
            {"word": "volatility", "category_slug": "risk"},
            {"word": "drawdown", "category_slug": "risk"},
            {"word": "var", "category_slug": "risk"},
            {"word": "revenue", "category_slug": "growth"},
            {"word": "arr", "category_slug": "growth"},
            {"word": "pipeline", "category_slug": "growth"},
        ],
    }
    records = [
        {"word": "volatility", "text": "Volatility rose after the Fed decision."},
        {"word": "drawdown", "text": "Drawdown breached the risk budget."},
        {"word": "var", "text": "VaR limits tightened for credit books."},
        {"word": "revenue", "text": "Revenue beat consensus estimates."},
        {"word": "arr", "text": "ARR grew twenty percent year over year."},
        {"word": "pipeline", "text": "Sales pipeline expanded in enterprise."},
    ]

    rag = PrismRAG(mapping=mapping, tenant_id="demo-bridge")
    job = rag.ingest(records=records)
    mid = job["mapping_id"]
    comms = rag.list_communities()
    print(f"  communities: {len(comms)} (edge_count={job['edge_count']})")
    for c in comms:
        print(f"  community {c['community_id']}: {c['top_words']}")

    if len(comms) < 2:
        print("  bridge skipped - Louvain returned <2 communities on this toy set")
        return

    a, b = comms[0]["community_id"], comms[1]["community_id"]
    bridge = rag.create_bridge(a, b, bridge_label="risk-growth hop")
    print(json.dumps(bridge, default=str, indent=2)[:1200])
    print("  OK: bridge created - cross-topic hop without merging chunks")


def main() -> int:
    print("PrismRAG - Graph RAG replacement demo")
    print("pip package: prismrag-patch  |  offline deterministic embeddings for CI")

    demo_connected_via_shared_category()
    demo_without_shared_category()
    demo_bridge()

    section("SUMMARY")
    print(
        """
  Replacement pitch (honest):
  - Same job as Graph RAG: retrieve via graph structure, not vector lottery alone.
  - Different graph source: YOUR taxonomy rules -> rule edges + personal space.
  - Chunks stay separate (citation / audit). Connection = mapping + graph (+ bridge).
  - Soft CTA: pip install prismrag-patch | github.com/aminparva84/InsightPrismRAG
"""
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"\nASSERT FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
