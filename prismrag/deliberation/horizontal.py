"""
Deliberation — Phase 1: Horizontal domain discovery.

Given a user question, finds the top N domains/categories that are
relevant. Searches three sources in parallel and merges results:

  1. LLM (Gemini)         — "what fields of knowledge bear on this question?"
  2. PrismRAG KB          — community labels from the tenant's knowledge graph
  3. Built-in domain list — fallback taxonomy when neither is configured

Returns a ranked list of Domain objects, each with a relevance score
and the rationale for inclusion.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Domain:
    rank:            int
    name:            str
    slug:            str
    relevance_score: float
    rationale:       str
    source:          str  # llm | kb | builtin | hybrid


# ── Built-in fallback taxonomy ────────────────────────────────────────────────
# Used when neither Gemini nor a KB is available.
_BUILTIN_DOMAINS = [
    "Economics", "Psychology", "Law & Regulation", "Technology",
    "Medicine & Health", "Philosophy & Ethics", "Political Science",
    "Environmental Science", "History", "Sociology", "Mathematics",
    "Physics", "Chemistry", "Biology", "Business Strategy",
]


# ── LLM horizontal discovery ──────────────────────────────────────────────────

_DISCOVER_PROMPT = """\
You are a domain analyst. Given the user question below, identify the TOP {n} academic
and professional domains that are MOST relevant for a multi-expert deliberation panel.

For each domain return:
- name: concise domain name (e.g. "Behavioral Economics", "Contract Law")
- slug: snake_case version (e.g. "behavioral_economics", "contract_law")
- relevance_score: 0.0–1.0 (how central this domain is to answering the question)
- rationale: one sentence explaining why this domain matters for this question

Return ONLY a JSON array with exactly {n} objects, ordered by relevance descending.
No markdown fences, no prose, just the array.

QUESTION: {question}
"""


def discover_via_llm(question: str, n: int = 7) -> list[Domain]:
    """Ask Gemini to identify the top N relevant domains for the question."""
    try:
        import google.generativeai as genai
        import os
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = _DISCOVER_PROMPT.format(question=question, n=n)
        resp = model.generate_content(prompt)
        raw = (resp.text or "").strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
        items = json.loads(raw)
        domains = []
        for i, item in enumerate(items[:n], start=1):
            domains.append(Domain(
                rank=i,
                name=item.get("name", f"Domain {i}"),
                slug=item.get("slug", f"domain_{i}"),
                relevance_score=float(item.get("relevance_score", 0.5)),
                rationale=item.get("rationale", ""),
                source="llm",
            ))
        return domains
    except Exception:
        return []


# ── KB community horizontal search ───────────────────────────────────────────

def discover_via_kb(
    question: str,
    tenant_id: str,
    mapping_id: Optional[str],
    n: int = 7,
) -> list[Domain]:
    """
    Search PrismRAG community labels for domains relevant to the question.
    Uses the community centroid HNSW index — no LLM call needed.
    """
    try:
        from prismrag.retrieval.search import retrieve
        result = retrieve(
            tenant_id=tenant_id,
            query=question,
            mapping_id=mapping_id,
            top_k=n * 3,  # over-fetch, then deduplicate by community
        )
        seen_communities: dict[str, float] = {}
        for hit in result.get("hits", []):
            label = hit.get("community_label") or hit.get("category") or ""
            score = float(hit.get("score", 0))
            if label and label not in seen_communities:
                seen_communities[label] = score
            elif label and score > seen_communities.get(label, 0):
                seen_communities[label] = score

        domains = []
        for i, (label, score) in enumerate(
            sorted(seen_communities.items(), key=lambda x: -x[1])[:n], start=1
        ):
            slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
            domains.append(Domain(
                rank=i,
                name=label,
                slug=slug,
                relevance_score=score,
                rationale=f"Top community cluster in your knowledge graph (score={score:.3f})",
                source="kb",
            ))
        return domains
    except Exception:
        return []


# ── Merge + rank ──────────────────────────────────────────────────────────────

def _slug_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def discover_domains(
    question: str,
    n: int = 7,
    tenant_id: Optional[str] = None,
    mapping_id: Optional[str] = None,
) -> list[Domain]:
    """
    Main entry point. Runs LLM + KB discovery in parallel, merges, deduplicates,
    and returns the top N domains ranked by relevance.
    """
    import concurrent.futures

    futures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures["llm"] = pool.submit(discover_via_llm, question, n)
        if tenant_id:
            futures["kb"] = pool.submit(discover_via_kb, question, tenant_id, mapping_id, n)

    llm_results = futures["llm"].result()
    kb_results  = futures["kb"].result() if "kb" in futures else []

    # Merge: if same slug appears in both, boost score and mark source=hybrid
    merged: dict[str, Domain] = {}

    for d in llm_results:
        key = _slug_key(d.slug)
        merged[key] = d

    for d in kb_results:
        key = _slug_key(d.slug)
        if key in merged:
            existing = merged[key]
            # Boost score by 15% for appearing in both sources
            merged[key] = Domain(
                rank=existing.rank,
                name=existing.name,
                slug=existing.slug,
                relevance_score=min(1.0, existing.relevance_score * 1.15),
                rationale=existing.rationale + f" [Also in KB: {d.rationale}]",
                source="hybrid",
            )
        else:
            merged[key] = d

    # Fallback: if nothing found, use built-in taxonomy
    if not merged:
        for i, name in enumerate(_BUILTIN_DOMAINS[:n], start=1):
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            merged[slug] = Domain(
                rank=i, name=name, slug=slug,
                relevance_score=0.5 - (i * 0.03),
                rationale="General domain from built-in taxonomy",
                source="builtin",
            )

    # Re-rank by score, take top N
    ranked = sorted(merged.values(), key=lambda d: -d.relevance_score)[:n]
    for i, d in enumerate(ranked, start=1):
        d.rank = i
    return ranked
