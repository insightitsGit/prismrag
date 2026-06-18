"""
Deliberation — Full pipeline engine.

Orchestrates the three phases and persists everything to Postgres:
  1. Horizontal: discover_domains()
  2. Vertical:   query_all_domains()
  3. Synthesis:  synthesize()

Public API:
  create_session()   → session_id
  run_deliberation() → full result dict (also persisted)
  get_session()      → current state + results from DB
  run_followup()     → follow-up question on an existing session
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from prismrag.deliberation.horizontal import Domain, discover_domains
from prismrag.deliberation.vertical import VerticalResult, query_all_domains
from prismrag.deliberation.synthesis import SynthesisResult, synthesize


# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    from prismrag.db import get_conn
    return get_conn()

def _rel(conn):
    from prismrag.db import release_conn
    release_conn(conn)

def _set_status(session_id: str, status: str) -> None:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prismrag.deliberation_session "
            "SET status = %s, updated_at = now() WHERE id = %s",
            (status, session_id),
        )
        conn.commit()
    finally:
        _rel(conn)


# ── Session management ────────────────────────────────────────────────────────

def create_session(
    question: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    title: Optional[str] = None,
    domain_count: int = 7,
) -> str:
    """Create a new deliberation session. Returns session_id."""
    session_id = str(uuid.uuid4())
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prismrag.deliberation_session
                (id, user_id, tenant_id, title, question, domain_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session_id, user_id, tenant_id,
             title or question[:120], question, domain_count),
        )
        conn.commit()
    finally:
        _rel(conn)
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """Return full session state including domains, verticals, and synthesis."""
    conn = _conn()
    try:
        cur = conn.cursor()

        # Session
        cur.execute(
            "SELECT id, user_id, tenant_id, title, status, question, domain_count, "
            "created_at, updated_at FROM prismrag.deliberation_session WHERE id = %s",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        session: dict = {
            "session_id":   str(row[0]),
            "user_id":      str(row[1]) if row[1] else None,
            "tenant_id":    str(row[2]) if row[2] else None,
            "title":        row[3],
            "status":       row[4],
            "question":     row[5],
            "domain_count": row[6],
            "created_at":   row[7].isoformat() if row[7] else None,
            "updated_at":   row[8].isoformat() if row[8] else None,
        }

        # Domains
        cur.execute(
            "SELECT id, rank, name, slug, relevance_score, rationale, source "
            "FROM prismrag.deliberation_domain WHERE session_id = %s ORDER BY rank",
            (session_id,),
        )
        session["domains"] = [
            {"id": str(r[0]), "rank": r[1], "name": r[2], "slug": r[3],
             "relevance_score": r[4], "rationale": r[5], "source": r[6]}
            for r in cur.fetchall()
        ]

        # Verticals
        cur.execute(
            "SELECT dv.id, dd.name, dv.query_text, dv.findings, dv.kb_hits, "
            "dv.confidence, dv.tokens_used, dv.latency_ms "
            "FROM prismrag.deliberation_vertical dv "
            "JOIN prismrag.deliberation_domain dd ON dd.id = dv.domain_id "
            "WHERE dv.session_id = %s "
            "ORDER BY dd.rank",
            (session_id,),
        )
        session["verticals"] = [
            {"id": str(r[0]), "domain": r[1], "query": r[2], "findings": r[3],
             "kb_hits": r[4] or [], "confidence": r[5],
             "tokens_used": r[6], "latency_ms": r[7]}
            for r in cur.fetchall()
        ]

        # Synthesis
        cur.execute(
            "SELECT agreements, conflicts, unique_insights, final_answer, "
            "confidence, synthesis_type, contributing_domains "
            "FROM prismrag.deliberation_synthesis WHERE session_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        synth_row = cur.fetchone()
        session["synthesis"] = {
            "agreements":           synth_row[0],
            "conflicts":            synth_row[1],
            "unique_insights":      synth_row[2],
            "final_answer":         synth_row[3],
            "confidence":           synth_row[4],
            "synthesis_type":       synth_row[5],
            "contributing_domains": synth_row[6] or [],
        } if synth_row else None

        # Follow-ups
        cur.execute(
            "SELECT question, answer, created_at FROM prismrag.deliberation_followup "
            "WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
        session["followups"] = [
            {"question": r[0], "answer": r[1],
             "created_at": r[2].isoformat() if r[2] else None}
            for r in cur.fetchall()
        ]

        return session
    finally:
        _rel(conn)


# ── Persist helpers ───────────────────────────────────────────────────────────

def _persist_domains(session_id: str, domains: list[Domain]) -> dict[str, str]:
    """Returns {slug: domain_db_id}"""
    conn = _conn()
    id_map: dict[str, str] = {}
    try:
        cur = conn.cursor()
        for d in domains:
            domain_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO prismrag.deliberation_domain
                    (id, session_id, rank, name, slug, relevance_score, rationale, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (domain_id, session_id, d.rank, d.name, d.slug,
                 d.relevance_score, d.rationale, d.source),
            )
            id_map[d.slug] = domain_id
        conn.commit()
    finally:
        _rel(conn)
    return id_map


def _persist_verticals(
    session_id: str,
    results: list[VerticalResult],
    domain_id_map: dict[str, str],
) -> None:
    import json as _json
    conn = _conn()
    try:
        cur = conn.cursor()
        for r in results:
            domain_db_id = domain_id_map.get(r.domain.slug)
            if not domain_db_id:
                continue
            cur.execute(
                """
                INSERT INTO prismrag.deliberation_vertical
                    (id, session_id, domain_id, query_text, findings,
                     kb_hits, confidence, tokens_used, latency_ms)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (str(uuid.uuid4()), session_id, domain_db_id,
                 r.query_text, r.findings or r.error or "",
                 _json.dumps(r.kb_hits), r.confidence,
                 r.tokens_used, r.latency_ms),
            )
        conn.commit()
    finally:
        _rel(conn)


def _persist_synthesis(session_id: str, synth: SynthesisResult) -> None:
    import json as _json
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prismrag.deliberation_synthesis
                (id, session_id, synthesis_type, agreements, conflicts,
                 unique_insights, final_answer, confidence, contributing_domains)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (str(uuid.uuid4()), session_id, synth.synthesis_type,
             synth.agreements, synth.conflicts, synth.unique_insights,
             synth.final_answer, synth.confidence,
             _json.dumps(synth.contributing_domains)),
        )
        conn.commit()
    finally:
        _rel(conn)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_deliberation(
    session_id: str,
    question: str,
    domain_count: int = 7,
    tenant_id: Optional[str] = None,
    mapping_id: Optional[str] = None,
) -> dict:
    """
    Execute the full three-phase pipeline synchronously.
    Updates session status at each phase.
    Returns the complete result dict (same shape as get_session()).
    """
    # Phase 1: Horizontal domain discovery
    _set_status(session_id, "discovering")
    domains = discover_domains(
        question=question,
        n=domain_count,
        tenant_id=tenant_id,
        mapping_id=mapping_id,
    )
    domain_id_map = _persist_domains(session_id, domains)

    # Phase 2: Vertical deep queries (all domains in parallel)
    _set_status(session_id, "querying")
    vertical_results = query_all_domains(
        question=question,
        domains=domains,
        tenant_id=tenant_id,
        mapping_id=mapping_id,
        max_workers=min(domain_count, 7),
    )
    _persist_verticals(session_id, vertical_results, domain_id_map)

    # Phase 3: Deliberation synthesis
    _set_status(session_id, "synthesizing")
    synth = synthesize(question=question, vertical_results=vertical_results)
    _persist_synthesis(session_id, synth)

    _set_status(session_id, "done")

    return get_session(session_id)  # type: ignore[return-value]


def run_deliberation_bg(session_id: str, **kwargs) -> None:
    """Fire-and-forget wrapper for async runs."""
    def _run():
        try:
            run_deliberation(session_id=session_id, **kwargs)
        except Exception as exc:
            try:
                _set_status(session_id, "failed")
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


# ── Follow-up ─────────────────────────────────────────────────────────────────

_FOLLOWUP_PROMPT = """\
You are the Master Deliberator. A deliberation panel has already analysed the original question:

ORIGINAL QUESTION: {original_question}

DELIBERATION SYNTHESIS:
{synthesis}

The user now asks a follow-up:
FOLLOW-UP: {followup_question}

Answer the follow-up drawing on the panel's findings. If the follow-up introduces a genuinely
new angle not covered in the original deliberation, note which domains would need to weigh in.
Be concise and direct.
"""


def run_followup(
    session_id: str,
    followup_question: str,
) -> dict:
    """Run a follow-up question against an existing deliberated session."""
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    if session["status"] != "done":
        raise ValueError("Session must be in 'done' state before follow-up")

    synth = session.get("synthesis") or {}
    synthesis_text = (
        f"Final Answer: {synth.get('final_answer', '')}\n\n"
        f"Agreements: {synth.get('agreements', '')}\n\n"
        f"Conflicts: {synth.get('conflicts', '')}"
    )

    prompt = _FOLLOWUP_PROMPT.format(
        original_question=session["question"],
        synthesis=synthesis_text,
        followup_question=followup_question,
    )

    try:
        import os
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        from prismrag.config import GEMINI_LLM_MODEL
        model = genai.GenerativeModel(GEMINI_LLM_MODEL)
        resp = model.generate_content(prompt)
        answer = resp.text or ""
    except Exception as exc:
        answer = f"Error generating follow-up response: {exc}"

    # Persist
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prismrag.deliberation_followup "
            "(id, session_id, question, answer) VALUES (%s, %s, %s, %s)",
            (str(uuid.uuid4()), session_id, followup_question, answer),
        )
        conn.commit()
    finally:
        _rel(conn)

    return {"question": followup_question, "answer": answer}
