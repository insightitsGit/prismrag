"""
PrismRAG — Playground API routes.

These endpoints power the ephemeral playground page.  No data is persisted
beyond the session: tenant cleanup is triggered by the browser on tab close.

POST   /api/v1/prismrag/playground/chat   — RAG-grounded Gemini answer
DELETE /api/v1/prismrag/playground/{id}   — soft-delete ephemeral tenant (alias)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from prismrag.auth.auth import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prismrag/playground", tags=["Playground"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    context: str = Field(default="", max_length=30_000)
    tenant_id: str = Field(...)
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    model: str
    grounded: bool
    chunk_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gemini_chat(query: str, context: str) -> str:
    """Call Gemini 2.0 Flash with a RAG-grounded system prompt."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # Graceful fallback: format the top chunks as a structured reply
        if not context.strip():
            return "No relevant content found in your index for that query."
        lines = [c.strip() for c in context.split("\n\n") if c.strip()][:3]
        return (
            "Based on your indexed content:\n\n"
            + "\n\n".join(f"**[{i+1}]** {line[:300]}{'…' if len(line) > 300 else ''}"
                         for i, line in enumerate(lines))
            + f"\n\n*{len(lines)} source(s) retrieved.*"
        )

    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        system = (
            "You are a helpful assistant that answers questions STRICTLY based on "
            "the provided context chunks. If the context does not contain enough "
            "information to answer, say so honestly. Do not hallucinate facts.\n\n"
            "CONTEXT:\n" + context
        )
        resp = model.generate_content([system, f"QUESTION: {query}"])
        return resp.text or "No answer generated."
    except ImportError:
        log.warning("google-generativeai not installed; using fallback response")
        return _gemini_fallback(query, context)
    except Exception as exc:
        log.error("Gemini chat error: %s", exc)
        return _gemini_fallback(query, context)


def _gemini_fallback(query: str, context: str) -> str:
    if not context.strip():
        return "No relevant content found in your index for that query."
    lines = [c.strip() for c in context.split("\n\n") if c.strip()][:3]
    return (
        "Based on your indexed content:\n\n"
        + "\n\n".join(f"**[{i+1}]** {line[:300]}{'…' if len(line) > 300 else ''}"
                     for i, line in enumerate(lines))
        + f"\n\n*{len(lines)} source(s) retrieved.*"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def playground_chat(
    body: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    """
    Generate a RAG-grounded answer using Gemini.

    The caller is responsible for sending the retrieved context chunks
    (from /api/v1/prismrag/search) in the `context` field.
    This endpoint is intentionally lightweight — no quota charge applies
    to playground sessions.
    """
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty")

    answer = _gemini_chat(body.query, body.context)
    grounded = bool(body.context.strip())
    chunk_count = len([c for c in body.context.split("\n\n") if c.strip()])

    return ChatResponse(
        answer=answer,
        model="gemini-2.0-flash-exp",
        grounded=grounded,
        chunk_count=chunk_count,
    )


@router.delete("/{tenant_id}", status_code=204)
async def delete_playground_session(
    tenant_id: str,
    user: dict = Depends(get_current_user),
) -> None:
    """
    Soft-delete an ephemeral playground tenant.
    Called by the browser's beforeunload handler.
    Non-fatal if tenant doesn't exist or belongs to another user.
    """
    from prismrag.db import get_conn, release_conn
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Only delete tenants owned by this user AND named 'playground-*'
        cur.execute("""
            DELETE FROM prismrag.tenant
            WHERE id = %s
              AND lower(owner_email) = lower(%s)
              AND name LIKE 'playground-%%'
        """, (tenant_id, user["email"]))
        conn.commit()
        log.info("Playground tenant %s deleted for %s", tenant_id, user["email"])
    except Exception as exc:
        log.warning("Playground tenant cleanup failed (non-fatal): %s", exc)
        if conn:
            conn.rollback()
    finally:
        release_conn(conn)
