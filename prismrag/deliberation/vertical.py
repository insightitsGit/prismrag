"""
Deliberation — Phase 2: Vertical deep queries.

For each discovered domain, runs a targeted deep query:
  - Constructs a domain-expert persona prompt
  - Optionally searches PrismRAG KB with category_filter
  - Calls Gemini with KB context injected
  - Returns structured findings with confidence estimate

All domains are queried in parallel (ThreadPoolExecutor).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from prismrag.deliberation.horizontal import Domain


@dataclass
class VerticalResult:
    domain:     Domain
    query_text: str
    findings:   str
    kb_hits:    list[dict]   # PrismRAG search hits used as context
    confidence: float        # 0-1
    tokens_used: int
    latency_ms: int
    error:      Optional[str] = None


_VERTICAL_PROMPT = """\
You are a world-class expert in {domain_name}.

Your task: answer the user's question strictly from the lens of {domain_name}.
Be specific, cite mechanisms, principles, or evidence within this domain.
Do NOT hedge into other domains — stay in your lane.
End with a confidence score: "CONFIDENCE: X.X" where X.X is 0.0–1.0 representing
how central this domain's expertise is to answering the question.

{kb_context}

USER QUESTION: {question}

DOMAIN PERSPECTIVE ({domain_name}):"""


def _build_kb_context(hits: list[dict]) -> str:
    if not hits:
        return ""
    lines = ["RELEVANT KNOWLEDGE BASE EXCERPTS (from your organization's corpus):"]
    for h in hits[:5]:
        text = (h.get("text") or h.get("word") or "").strip()
        if text:
            lines.append(f"  • {text}")
    return "\n".join(lines) + "\n\n"


def _extract_confidence(text: str) -> tuple[str, float]:
    """Parse CONFIDENCE: X.X from end of response, return (clean_text, confidence)."""
    import re
    match = re.search(r"CONFIDENCE:\s*([01]?\.\d+)", text, re.IGNORECASE)
    if match:
        conf = float(match.group(1))
        clean = text[:match.start()].strip()
        return clean, min(1.0, max(0.0, conf))
    return text.strip(), 0.7  # default confidence


def query_domain(
    question: str,
    domain: Domain,
    tenant_id: Optional[str],
    mapping_id: Optional[str],
) -> VerticalResult:
    """Run a single deep vertical query for one domain."""
    t0 = time.perf_counter()
    kb_hits: list[dict] = []

    # 1. KB search for this domain (if workspace configured)
    if tenant_id:
        try:
            from prismrag.retrieval.search import retrieve
            kb_result = retrieve(
                tenant_id=tenant_id,
                query=f"{domain.name}: {question}",
                mapping_id=mapping_id,
                top_k=5,
                category_filter=domain.slug,
            )
            kb_hits = kb_result.get("hits", [])
        except Exception:
            kb_hits = []

    # 2. Construct targeted prompt
    kb_context = _build_kb_context(kb_hits)
    query_text = f"{domain.name}: {question}"
    prompt = _VERTICAL_PROMPT.format(
        domain_name=domain.name,
        question=question,
        kb_context=kb_context,
    )

    # 3. Call LLM
    try:
        import os
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        from prismrag.config import GEMINI_LLM_MODEL
        model = genai.GenerativeModel(GEMINI_LLM_MODEL)
        resp = model.generate_content(prompt)
        raw_text = resp.text or ""
        tokens = getattr(resp.usage_metadata, "total_token_count", 0) if hasattr(resp, "usage_metadata") else 0
        findings, confidence = _extract_confidence(raw_text)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return VerticalResult(
            domain=domain,
            query_text=query_text,
            findings=findings,
            kb_hits=kb_hits,
            confidence=confidence,
            tokens_used=tokens,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return VerticalResult(
            domain=domain,
            query_text=query_text,
            findings="",
            kb_hits=kb_hits,
            confidence=0.0,
            tokens_used=0,
            latency_ms=latency_ms,
            error=str(exc),
        )


def query_all_domains(
    question: str,
    domains: list[Domain],
    tenant_id: Optional[str] = None,
    mapping_id: Optional[str] = None,
    max_workers: int = 7,
) -> list[VerticalResult]:
    """
    Query all domains in parallel. Returns results in domain rank order.
    Failed domains are included with error field set — never skipped.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_domain = {
            pool.submit(query_domain, question, domain, tenant_id, mapping_id): domain
            for domain in domains
        }
        results_map: dict[int, VerticalResult] = {}
        for future in concurrent.futures.as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                result = future.result()
            except Exception as exc:
                result = VerticalResult(
                    domain=domain,
                    query_text=question,
                    findings="",
                    kb_hits=[],
                    confidence=0.0,
                    tokens_used=0,
                    latency_ms=0,
                    error=str(exc),
                )
            results_map[domain.rank] = result

    # Return in rank order
    return [results_map[d.rank] for d in sorted(domains, key=lambda d: d.rank)
            if d.rank in results_map]
