"""Shared helpers for integration tests."""
from __future__ import annotations

import time

import pytest
import requests

TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "stale"})


def parse_error(data: dict) -> str:
    detail = data.get("detail", "Request failed")
    if isinstance(detail, list):
        return "; ".join(str(d.get("msg", d)) for d in detail)
    return str(detail)


def login(api: requests.Session, email: str, password: str) -> dict:
    r = api.post(api.url("/api/v1/auth/login"), json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    if data.get("mfa_required"):
        pytest.skip("QA user has MFA enabled — disable MFA or use a fresh QA email")
    assert data.get("token"), f"No token in login response: {data}"
    return data


def poll_job(
    api: requests.Session,
    rag_api: str,
    job_id: str,
    *,
    timeout_s: int = 180,
    interval_s: float = 2.0,
) -> dict:
    """Poll ingest job until terminal status."""
    deadline = time.time() + timeout_s
    last_status = ""
    while time.time() < deadline:
        r = api.get(api.url(f"{rag_api}/jobs/{job_id}"))
        assert r.status_code == 200, r.text
        body = r.json()
        last_status = body.get("status", "")
        if last_status in TERMINAL_JOB_STATUSES:
            if last_status == "failed":
                pytest.fail(f"Job {job_id} failed: {body}")
            if last_status == "stale":
                pytest.fail(f"Job {job_id} went stale: {body}")
            return body
        if last_status == "queued" and time.time() > deadline - timeout_s + 30:
            pytest.skip(
                "Job still queued — start the job worker (run-local.bat) or set "
                "PRISMRAG_USE_JOB_QUEUE=false on the API server"
            )
        time.sleep(interval_s)
    pytest.fail(f"Job {job_id} timed out (last status={last_status})")


def search_sync(
    api: requests.Session,
    rag_api: str,
    tenant_id: str,
    query: str,
    **extra,
) -> dict:
    """Run search with wait=true (synchronous)."""
    payload = {"tenant_id": tenant_id, "query": query, "wait": True, **extra}
    r = api.post(api.url(f"{rag_api}/search"), json=payload)
    if r.status_code == 202:
        task_id = r.json().get("task_id")
        return poll_search_task(api, rag_api, task_id)
    assert r.status_code == 200, f"Search failed: {r.status_code} {r.text}"
    return r.json()


def poll_search_task(
    api: requests.Session,
    rag_api: str,
    task_id: str,
    *,
    timeout_s: int = 60,
) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = api.get(api.url(f"{rag_api}/search/tasks/{task_id}"))
        assert r.status_code == 200, r.text
        body = r.json()
        if body.get("status") == "completed":
            return body.get("result") or body
        if body.get("status") == "failed":
            pytest.fail(f"Search task failed: {body}")
        time.sleep(1)
    pytest.fail(f"Search task {task_id} timed out")
