"""
PrismRAG — Large file upload strategy.

Size tiers:
  < 1 MB       → inline (current path in routes.py)
  1 MB–500 MB  → Azure Blob Storage presigned SAS URL → Service Bus → worker
  > 500 MB     → Blob Storage + streaming chunk reader in worker (never fully in memory)

This module provides:
  generate_upload_url()  — creates a SAS URL, registers the file in large_file_upload
  poll_blob_and_enqueue()  — worker checks if blob arrived, sends job to Service Bus
  process_large_file()   — worker streams the blob and runs the ingest pipeline

Required env vars:
  AZURE_STORAGE_CONNECTION_STRING
  AZURE_STORAGE_CONTAINER   (default: prismrag-uploads)
  AZURE_SERVICE_BUS_CONNECTION_STRING
  AZURE_SERVICE_BUS_QUEUE   (default: prismrag-jobs)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

_CONTAINER    = os.getenv("AZURE_STORAGE_CONTAINER", "prismrag-uploads")
_SAS_EXPIRY_H = int(os.getenv("BLOB_SAS_EXPIRY_HOURS", "4"))

# Threshold above which we switch to large-file path (bytes)
LARGE_FILE_THRESHOLD = 1_000_000       # 1 MB
STREAM_THRESHOLD     = 500_000_000     # 500 MB


def generate_upload_url(
    user_id: str,
    tenant_id: str,
    original_name: str,
    file_size_bytes: int | None = None,
) -> dict:
    """
    Creates a write-only Azure Blob SAS URL valid for _SAS_EXPIRY_H hours.
    Registers the pending upload in large_file_upload.
    Returns the URL for the client to PUT the file directly to Azure.
    """
    try:
        from azure.storage.blob import (
            BlobServiceClient, BlobSasPermissions, generate_blob_sas,
        )
    except ImportError:
        raise RuntimeError(
            "azure-storage-blob not installed. "
            "pip install azure-storage-blob azure-servicebus"
        )

    conn_str   = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    blob_name  = f"{tenant_id}/{uuid.uuid4()}_{original_name}"
    expiry     = datetime.now(timezone.utc) + timedelta(hours=_SAS_EXPIRY_H)

    client     = BlobServiceClient.from_connection_string(conn_str)
    account    = client.account_name
    account_key = client.credential.account_key  # type: ignore[attr-defined]

    sas_token = generate_blob_sas(
        account_name=account,
        container_name=_CONTAINER,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(write=True, create=True),
        expiry=expiry,
    )

    blob_url  = f"https://{account}.blob.core.windows.net/{_CONTAINER}/{blob_name}"
    upload_url = f"{blob_url}?{sas_token}"

    # Register in DB
    upload_id = str(uuid.uuid4())
    _register_upload(
        upload_id=upload_id,
        user_id=user_id,
        tenant_id=tenant_id,
        blob_url=blob_url,
        blob_name=blob_name,
        original_name=original_name,
        file_size_bytes=file_size_bytes,
        sas_expires_at=expiry,
    )

    return {
        "upload_id":  upload_id,
        "upload_url": upload_url,      # client PUTs file here
        "blob_name":  blob_name,
        "expires_at": expiry.isoformat(),
        "max_size_bytes": 500_000_000,
        "instructions": (
            "PUT your file to upload_url with Content-Type: application/octet-stream. "
            "Then POST to /api/prismrag/jobs/large with {upload_id, tenant_id, strategy}."
        ),
    }


def enqueue_large_job(
    upload_id: str,
    tenant_id: str,
    strategy: str,
    user_id: str,
) -> str:
    """
    Called after client confirms upload is done.
    Marks upload as 'uploaded', creates a job record, sends to Service Bus.
    Returns job_id.
    """
    from prismrag.db import get_conn, release_conn

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT blob_name, original_name, file_size_bytes "
            "FROM prismrag.large_file_upload WHERE id = %s AND user_id = %s",
            (upload_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Upload not found or not owned by user")

        blob_name, original_name, size_bytes = row
        job_id = str(uuid.uuid4())

        # Mark as uploaded
        cur.execute(
            "UPDATE prismrag.large_file_upload "
            "SET status = 'uploaded', job_id = %s, updated_at = now() WHERE id = %s",
            (job_id, upload_id),
        )
        conn.commit()
    finally:
        release_conn(conn)

    # Send to Azure Service Bus
    message = json.dumps({
        "job_id":    job_id,
        "upload_id": upload_id,
        "tenant_id": tenant_id,
        "strategy":  strategy,
        "user_id":   user_id,
        "blob_name": blob_name,
        "size_bytes": size_bytes,
        "stream_mode": (size_bytes or 0) > STREAM_THRESHOLD,
    })
    _send_to_service_bus(message)
    return job_id


def process_large_file(message: dict) -> None:
    """
    Worker entry point — called when a Service Bus message is received.
    Streams blob into the ingest pipeline without loading it all into memory.
    """
    import io
    from azure.storage.blob import BlobServiceClient

    blob_name   = message["blob_name"]
    tenant_id   = message["tenant_id"]
    strategy    = message["strategy"]
    job_id      = message["job_id"]
    stream_mode = message.get("stream_mode", False)

    conn_str    = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    client      = BlobServiceClient.from_connection_string(conn_str)
    blob_client = client.get_blob_client(_CONTAINER, blob_name)

    if stream_mode:
        # > 500 MB: stream directly — never load full file into memory
        _process_streaming(blob_client, job_id, tenant_id, strategy)
    else:
        # 1 MB–500 MB: download to memory, run existing pipeline
        data = blob_client.download_blob().readall()
        from prismrag.pipeline.job import run_job
        from prismrag.models import (
            FileSourceConfig, JobRequest, MappingConfigIn, SourceType
        )
        request = JobRequest(
            tenant_id=uuid.UUID(tenant_id),
            source_type=SourceType.file,
            strategy=strategy,
            file_config=FileSourceConfig(filename=blob_name.split("/")[-1]),
            mapping=MappingConfigIn(categories=[], rules=[]),
        )
        run_job(job_id, request, data)

    # Delete blob after processing (save storage cost)
    try:
        blob_client.delete_blob()
    except Exception:
        pass

    # Update large_file_upload status
    _mark_upload_done(message["upload_id"])


def _process_streaming(blob_client, job_id: str, tenant_id: str, strategy: str) -> None:
    """
    Streams a very large blob row-by-row through the pipeline.
    Memory footprint: one batch at a time (INGEST_BATCH_SIZE rows).
    """
    import csv
    import io
    from prismrag.config import INGEST_BATCH_SIZE
    from prismrag.embedding.gemini import embed_texts
    from prismrag.mapping.rules import RulesStrategy

    stream = blob_client.download_blob()

    # Load mapping strategy from DB (tenant's active mapping)
    strategy_obj = _load_active_strategy(tenant_id, strategy)

    batch_words: list[str] = []
    batch_texts: list[str] = []
    total = 0

    # Wrap stream in a text reader for CSV parsing
    text_stream = io.TextIOWrapper(stream.chunks(), encoding="utf-8", errors="replace")  # type: ignore[arg-type]

    reader = csv.DictReader(text_stream)
    for row in reader:
        word = (row.get("word") or row.get("Word") or "").strip()
        text = (row.get("text") or row.get("Text") or word).strip()
        if not word:
            continue
        batch_words.append(word)
        batch_texts.append(text)

        if len(batch_words) >= INGEST_BATCH_SIZE:
            _flush_stream_batch(batch_words, batch_texts, strategy_obj, tenant_id, job_id)
            total += len(batch_words)
            batch_words, batch_texts = [], []
            _update_job_progress(job_id, total)

    if batch_words:
        _flush_stream_batch(batch_words, batch_texts, strategy_obj, tenant_id, job_id)
        total += len(batch_words)

    _update_job_progress(job_id, total, done=True)


def _flush_stream_batch(words, texts, strategy_obj, tenant_id, job_id):
    from prismrag.embedding.gemini import embed_texts
    from prismrag.db import get_conn, release_conn, vector_to_pg

    sem_vecs = embed_texts(texts)
    results  = strategy_obj.assign_batch(list(zip(words, texts, sem_vecs)))

    conn = get_conn()
    try:
        cur = conn.cursor()
        rows = [
            (tenant_id, r.word, r.text, vector_to_pg(r.embedding),
             r.category_slug, vector_to_pg(r.sem_embedding) if r.sem_embedding is not None else None)
            for r in results
        ]
        cur.executemany(
            """
            INSERT INTO prismrag.chunk_embedding
                (tenant_id, word, text, embedding, category_slug, sem_embedding)
            VALUES (%s, %s, %s, %s::vector, %s, %s::vector)
            ON CONFLICT (tenant_id, word) DO UPDATE SET
                embedding     = EXCLUDED.embedding,
                category_slug = EXCLUDED.category_slug,
                sem_embedding = EXCLUDED.sem_embedding,
                updated_at    = now()
            """,
            rows,
        )
        conn.commit()
    finally:
        release_conn(conn)


def _load_active_strategy(tenant_id: str, strategy: str):
    from prismrag.mapping.rules import RulesStrategy
    from prismrag.db import get_conn, release_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM prismrag.mapping_version "
            "WHERE tenant_id = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (tenant_id,),
        )
        row = cur.fetchone()
        mapping_id = str(row[0]) if row else None
    finally:
        release_conn(conn)

    if mapping_id:
        return RulesStrategy.from_db(mapping_id)
    # No active mapping — create a minimal passthrough strategy
    from prismrag.mapping.base import MappingStrategy, MappingResult
    import numpy as np

    class PassthroughStrategy(MappingStrategy):
        def assign(self, word, text, sem_vec):
            return MappingResult(
                category_slug="default",
                embedding=sem_vec[:256] if len(sem_vec) >= 256 else np.pad(sem_vec, (0, 256 - len(sem_vec))),
                sem_embedding=sem_vec,
            )
        def assign_batch(self, items):
            return [self.assign(w, t, v) for w, t, v in items]

    return PassthroughStrategy()


def _update_job_progress(job_id: str, total: int, done: bool = False) -> None:
    from prismrag.db import get_conn, release_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prismrag.ingest_job SET records_written = %s, "
            "progress_pct = LEAST(99, %s), "
            "status = %s, updated_at = now() WHERE id = %s",
            (total, min(99, total // 100), "done" if done else "running", job_id),
        )
        conn.commit()
    finally:
        release_conn(conn)


def _register_upload(
    upload_id, user_id, tenant_id, blob_url,
    blob_name, original_name, file_size_bytes, sas_expires_at,
) -> None:
    from prismrag.db import get_conn, release_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prismrag.large_file_upload
                (id, user_id, tenant_id, blob_url, blob_container, blob_name,
                 original_name, file_size_bytes, sas_expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (upload_id, user_id, tenant_id, blob_url, _CONTAINER,
             blob_name, original_name, file_size_bytes, sas_expires_at),
        )
        conn.commit()
    finally:
        release_conn(conn)


def _mark_upload_done(upload_id: str) -> None:
    from prismrag.db import get_conn, release_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prismrag.large_file_upload SET status='done', updated_at=now() WHERE id=%s",
            (upload_id,),
        )
        conn.commit()
    finally:
        release_conn(conn)


def _send_to_service_bus(message: str) -> None:
    try:
        from azure.servicebus import ServiceBusClient, ServiceBusMessage
        conn_str   = os.environ["AZURE_SERVICE_BUS_CONNECTION_STRING"]
        queue_name = os.getenv("AZURE_SERVICE_BUS_QUEUE", "prismrag-jobs")
        with ServiceBusClient.from_connection_string(conn_str) as sb:
            with sb.get_queue_sender(queue_name) as sender:
                sender.send_messages(ServiceBusMessage(message))
    except ImportError:
        # Fallback: run synchronously (dev mode without Azure)
        import threading
        data = json.loads(message)
        threading.Thread(target=_dev_process_fallback, args=(data,), daemon=True).start()


def _dev_process_fallback(message: dict) -> None:
    """Dev fallback when Azure Service Bus is not configured."""
    try:
        process_large_file(message)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Dev fallback job failed: %s", exc)
