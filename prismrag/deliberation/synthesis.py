"""
Deliberation — Phase 3: Comparison and synthesis.

Takes the vertical results from all domains and produces:
  - agreements:       where multiple domains converge on the same point
  - conflicts:        genuine disagreements between domain perspectives
  - unique_insights:  things only one domain noticed
  - final_answer:     the synthesized response that integrates all perspectives
  - contributing_domains: ranked by how much each contributed

The synthesis prompt positions the LLM as a "Master deliberator" — the same
role as the Delllusion Master orchestrator, but now driven by structured
vertical results rather than free-form agent turns.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from prismrag.deliberation.vertical import VerticalResult


@dataclass
class SynthesisResult:
    agreements:           str
    conflicts:            str
    unique_insights:      str
    final_answer:         str
    confidence:           float
    synthesis_type:       str               # comparison | consensus | conflict | comprehensive
    contributing_domains: list[dict]        # [{name, weight, agreement_score}]


_SYNTHESIS_PROMPT = """\
You are the Master Deliberator. You have received expert analyses from {n_domains} domain specialists
on the following question:

QUESTION: {question}

--- DOMAIN EXPERT FINDINGS ---
{domain_findings}
--- END FINDINGS ---

Your job is to perform a structured deliberation:

1. AGREEMENTS — Where do two or more domains reach the same conclusion? List them as bullet points.
2. CONFLICTS — Where do domains genuinely disagree? Explain each conflict, which domain holds which view, and why.
3. UNIQUE INSIGHTS — What did individual domains surface that others missed?
4. FINAL ANSWER — Synthesize all perspectives into a cohesive, authoritative answer.
   Weight domains by their confidence scores. Do not just summarize — deliberate and conclude.

Then output exactly this JSON block (no markdown, no prose before or after):
{{
  "agreements": "...",
  "conflicts": "...",
  "unique_insights": "...",
  "final_answer": "...",
  "confidence": 0.0,
  "synthesis_type": "comparison|consensus|conflict|comprehensive",
  "contributing_domains": [
    {{"name": "Domain Name", "weight": 0.0, "agreement_score": 0.0}}
  ]
}}
"""


def _format_domain_findings(results: list[VerticalResult]) -> str:
    lines = []
    for r in results:
        if r.error or not r.findings:
            lines.append(
                f"[{r.domain.rank}. {r.domain.name}] — ERROR: {r.error or 'no findings'}"
            )
        else:
            lines.append(
                f"[{r.domain.rank}. {r.domain.name}] "
                f"(confidence={r.confidence:.2f}, relevance={r.domain.relevance_score:.2f})\n"
                f"{r.findings}\n"
            )
    return "\n".join(lines)


def synthesize(
    question: str,
    vertical_results: list[VerticalResult],
) -> SynthesisResult:
    """
    Run the Master deliberation synthesis over all vertical results.
    Returns a SynthesisResult with agreements, conflicts, unique insights, and final answer.
    """
    # Filter out completely failed domains
    valid = [r for r in vertical_results if r.findings and not r.error]
    failed = [r for r in vertical_results if not r.findings or r.error]

    if not valid:
        # All domains failed — return structured error
        return SynthesisResult(
            agreements="",
            conflicts="",
            unique_insights="",
            final_answer="Unable to synthesize: all domain queries failed. Check your LLM configuration.",
            confidence=0.0,
            synthesis_type="comparison",
            contributing_domains=[],
        )

    domain_findings = _format_domain_findings(valid)
    prompt = _SYNTHESIS_PROMPT.format(
        n_domains=len(valid),
        question=question,
        domain_findings=domain_findings,
    )

    try:
        import os
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(prompt)
        raw = (resp.text or "").strip()

        # Strip markdown fences
        import re
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()

        # Find the JSON block
        json_match = re.search(r"\{[\s\S]+\}", raw)
        if not json_match:
            raise ValueError("No JSON block in synthesis response")

        data = json.loads(json_match.group(0))

        return SynthesisResult(
            agreements=data.get("agreements", ""),
            conflicts=data.get("conflicts", ""),
            unique_insights=data.get("unique_insights", ""),
            final_answer=data.get("final_answer", ""),
            confidence=float(data.get("confidence", 0.7)),
            synthesis_type=data.get("synthesis_type", "comparison"),
            contributing_domains=data.get("contributing_domains", [
                {"name": r.domain.name, "weight": r.confidence, "agreement_score": r.confidence}
                for r in valid
            ]),
        )

    except Exception as exc:
        # Graceful fallback: concatenate findings as the final answer
        fallback_answer = "\n\n".join(
            f"**{r.domain.name}**: {r.findings[:600]}" for r in valid
        )
        return SynthesisResult(
            agreements="",
            conflicts="",
            unique_insights=f"Synthesis error: {exc}",
            final_answer=fallback_answer,
            confidence=0.4,
            synthesis_type="comparison",
            contributing_domains=[
                {"name": r.domain.name, "weight": r.confidence, "agreement_score": 0.5}
                for r in valid
            ],
        )
