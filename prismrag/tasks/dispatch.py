"""PrismRAG — Background task dispatch (thread pool + job queue)."""
from __future__ import annotations

import atexit
import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

_POOL_SIZE = int(os.getenv("PRISMRAG_WORKER_THREADS", "4"))
_executor = ThreadPoolExecutor(max_workers=_POOL_SIZE, thread_name_prefix="prismrag")
atexit.register(_executor.shutdown, wait=False)


def use_job_queue() -> bool:
    """Postgres job queue is on by default; set PRISMRAG_USE_JOB_QUEUE=false to disable."""
    raw = os.getenv("PRISMRAG_USE_JOB_QUEUE", "true").lower()
    return raw not in ("0", "false", "no", "off")


def run_in_thread(fn: Callable[..., Any], *args, **kwargs) -> None:
    """Fire-and-forget sync work on the shared thread pool (does not block the event loop)."""
    _executor.submit(_safe_run, fn, *args, **kwargs)


def _safe_run(fn: Callable[..., Any], *args, **kwargs) -> None:
    try:
        fn(*args, **kwargs)
    except Exception:
        logger.exception("Background task failed: %s", getattr(fn, "__name__", fn))


def dispatch_ingest(
    job_id: str,
    tenant_id: str,
    request,
    upload_bytes: bytes | None,
    user: dict | None,
) -> None:
    """
    Queue ingest for a worker process, or run on the API thread pool as fallback.
    Never runs inline on the HTTP request thread.
    """
    if use_job_queue():
        from prismrag.worker.job_worker import enqueue_job

        payload = request.model_dump(mode="json")
        upload_b64 = base64.b64encode(upload_bytes).decode() if upload_bytes else None
        enqueue_job(job_id, tenant_id, payload, upload_b64, user.get("id") if user else None)
        return

    run_in_thread(_run_ingest_job, job_id, request, upload_bytes, user)


def _run_ingest_job(
    job_id: str,
    request,
    upload_bytes: bytes | None,
    user: dict | None,
) -> None:
    from prismrag.pipeline.job import get_job, run_job
    from prismrag.metering.quota import check_and_record

    try:
        run_job(
            job_id,
            request,
            upload_bytes,
            user_id=user.get("id") if user else None,
            plan=user.get("plan", "free") if user else "free",
        )
        if user:
            job = get_job(job_id)
            chunks = job.get("recordsWritten", 0) if job else 0
            if chunks > 0:
                check_and_record(user, "ingest_chunk", chunks, str(request.tenant_id))
    except Exception:
        logger.exception("Ingest job %s failed in thread pool", job_id)


def dispatch_search_task(task_id: str, request_dict: dict, user: dict) -> None:
    """Run search in thread pool and persist result to search_task."""
    run_in_thread(_execute_search_task, task_id, request_dict, user)


def _execute_search_task(task_id: str, request_dict: dict, user: dict) -> None:
    from prismrag.retrieval.search import retrieve
    from prismrag.audit.results import log_search_result
    import time

    _update_search_task(task_id, status="running")
    t0 = time.perf_counter()
    try:
        result = retrieve(
            tenant_id=request_dict["tenant_id"],
            query=request_dict["query"],
            mapping_id=request_dict.get("mapping_id"),
            top_k=request_dict.get("top_k", 10),
            category_filter=request_dict.get("category_filter"),
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        log_search_result(
            user_id=user.get("id"),
            tenant_id=request_dict["tenant_id"],
            mapping_id=result.get("mapping_id"),
            query_text=request_dict["query"],
            query_embedding=None,
            top_k=request_dict.get("top_k", 10),
            category_filter=request_dict.get("category_filter"),
            results=result,
            retrieval_mode=result.get("retrieval_mode", "direct"),
            latency_ms=latency_ms,
            plan=user.get("plan", "free"),
        )
        _update_search_task(task_id, status="completed", result=result, latency_ms=latency_ms)
    except Exception as exc:
        logger.exception("Search task %s failed", task_id)
        _update_search_task(task_id, status="failed", error_message=str(exc)[:500])


def create_search_task(user_id: str, tenant_id: str, request_dict: dict) -> str:
    import json
    import uuid
    from prismrag.db import get_conn, release_conn

    task_id = str(uuid.uuid4())
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prismrag.search_task
                (id, user_id, tenant_id, request, status)
            VALUES (%s, %s, %s, %s::jsonb, 'pending')
            """,
            (task_id, user_id, tenant_id, json.dumps(request_dict)),
        )
        conn.commit()
    finally:
        release_conn(conn)
    return task_id


def get_search_task(task_id: str, user_id: str) -> dict | None:
    import json
    from prismrag.db import get_conn, release_conn

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id::text, tenant_id::text, status, request, result,
                   error_message, latency_ms, created_at, finished_at
            FROM prismrag.search_task WHERE id = %s
            """,
            (task_id,),
        )
        row = cur.fetchone()
    finally:
        release_conn(conn)

    if not row or row[0] != user_id:
        return None

    result = row[4]
    if isinstance(result, str):
        result = json.loads(result)

    return {
        "task_id": task_id,
        "tenant_id": row[1],
        "status": row[2],
        "request": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
        "result": result,
        "error_message": row[5],
        "latency_ms": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "finished_at": row[8].isoformat() if row[8] else None,
    }


def _update_search_task(
    task_id: str,
    *,
    status: str,
    result: dict | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
) -> None:
    import json
    from prismrag.db import get_conn, release_conn

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE prismrag.search_task
            SET status = %s,
                result = COALESCE(%s::jsonb, result),
                error_message = %s,
                latency_ms = COALESCE(%s, latency_ms),
                finished_at = CASE WHEN %s IN ('completed', 'failed') THEN now() ELSE finished_at END
            WHERE id = %s
            """,
            (
                status,
                json.dumps(result) if result is not None else None,
                error_message,
                latency_ms,
                status,
                task_id,
            ),
        )
        conn.commit()
    finally:
        release_conn(conn)
