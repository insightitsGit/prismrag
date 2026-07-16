"""Pytest checks for the Graph RAG replacement demo (CI-friendly)."""
from __future__ import annotations

from prismrag_patch import PrismRAG

from demo_taxonomy_connection import FINANCE_RECORDS, cosine
import numpy as np


def test_shared_category_creates_rule_edge_and_retrieves_both():
    mapping = {
        "categories": [
            {"slug": "risk", "label": "Risk & Compliance"},
            {"slug": "growth", "label": "Growth & Revenue"},
        ],
        "rules": [
            {"word": "volatility", "category_slug": "risk"},
            {"word": "drawdown", "category_slug": "risk"},
            {"word": "revenue", "category_slug": "growth"},
        ],
    }
    rag = PrismRAG(mapping=mapping, tenant_id="test-connected")
    job = rag.ingest(records=FINANCE_RECORDS)
    mid = job["mapping_id"]

    edges = rag.store.get_edges(rag.tenant_id, mid)
    rule = [
        e
        for e in edges
        if e.edge_type == "rule"
        and {e.from_word, e.to_word} == {"volatility", "drawdown"}
    ]
    assert rule, "expected volatility <-> drawdown rule edge"

    chunks = {c.chunk_ref: c for c in rag.store.all_chunks(rag.tenant_id, mid)}
    assert len(chunks["volatility"].embedding) == 256
    assert len(chunks["volatility"].sem_embedding) == 768

    same = cosine(
        np.asarray(chunks["volatility"].embedding, dtype=float),
        np.asarray(chunks["drawdown"].embedding, dtype=float),
    )
    cross = cosine(
        np.asarray(chunks["volatility"].embedding, dtype=float),
        np.asarray(chunks["revenue"].embedding, dtype=float),
    )
    assert same > cross

    hits = rag.search("What are the risk metrics for the portfolio?", top_k=5)
    refs = {h["chunk_ref"] for h in hits.get("results") or hits.get("hits") or []}
    assert {"volatility", "drawdown"} <= refs


def test_split_categories_have_no_rule_edge():
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
    rag = PrismRAG(mapping=mapping, tenant_id="test-split")
    job = rag.ingest(records=FINANCE_RECORDS)
    edges = rag.store.get_edges(rag.tenant_id, job["mapping_id"])
    rule = [
        e
        for e in edges
        if e.edge_type == "rule"
        and {e.from_word, e.to_word} == {"volatility", "drawdown"}
    ]
    assert not rule


def test_bridge_between_communities():
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
    rag = PrismRAG(mapping=mapping, tenant_id="test-bridge")
    rag.ingest(records=records)
    comms = rag.list_communities()
    assert len(comms) >= 2
    out = rag.create_bridge(
        comms[0]["community_id"],
        comms[1]["community_id"],
        bridge_label="risk-growth hop",
    )
    assert out.get("community_a") == comms[0]["community_id"]
    assert out.get("community_b") == comms[1]["community_id"]
