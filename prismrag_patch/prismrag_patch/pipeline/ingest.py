"""Ingest pipeline (parity with SaaS prismrag.pipeline.job core path)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from prismrag_patch.config import INGEST_BATCH_SIZE
from prismrag_patch.graph.builder import build_graph
from prismrag_patch.graph.community import build_communities, default_label_fn
from prismrag_patch.mapping.rules import RulesStrategy
from prismrag_patch.models import InlineRecord, JobStatus, MappingConfig
from prismrag_patch.store.memory import MemoryStore
from prismrag_patch.store.postgres import PostgresStore

logger = logging.getLogger(__name__)


def run_ingest(
    store: MemoryStore | PostgresStore,
    tenant_id: str,
    job_id: str,
    mapping: MappingConfig | dict[str, Any],
    records: list[InlineRecord],
    embed_fn: Callable[[list[str]], list[list[float] | None]] | None = None,
    strategy: str = "rules",
    label_fn: Callable | None = None,
) -> dict[str, Any]:
    """Execute full ingest: mapping → vectors → graph → communities."""
    store.update_job(
        job_id,
        status=JobStatus.running,
        started_at=datetime.now(timezone.utc),
        records_total=len(records),
    )
    mapping_cfg = mapping if isinstance(mapping, MappingConfig) else MappingConfig.from_dict(mapping)

    try:
        if not mapping_cfg.rules:
            raise ValueError("Mapping must contain at least one rule")

        mapping_id = store.persist_mapping(tenant_id, mapping_cfg, strategy)
        store.update_job(job_id, mapping_id=mapping_id, progress_pct=15)

        rules_strat = RulesStrategy(mapping_cfg, embed_fn=embed_fn)
        written = 0
        batch: list[tuple[str, str, str | None]] = []

        for rec in records:
            text = rec.text or rec.word.replace("_", " ")
            batch.append((rec.word, text, rec.category_hint))
            if len(batch) >= INGEST_BATCH_SIZE:
                written += _write_batch(store, tenant_id, mapping_id, rules_strat, batch)
                batch = []
                pct = min(80, 15 + int(65 * written / max(len(records), 1)))
                store.update_job(job_id, records_written=written, progress_pct=pct)

        if batch:
            written += _write_batch(store, tenant_id, mapping_id, rules_strat, batch)

        store.update_job(job_id, records_written=written, progress_pct=85)

        edge_count = build_graph(store, tenant_id, mapping_id)
        logger.info("Built %d graph edges", edge_count)

        comm_count = build_communities(
            store, tenant_id, mapping_id,
            label_fn=label_fn or default_label_fn,
        )
        logger.info("Built %d communities", comm_count)

        store.update_job(
            job_id,
            status=JobStatus.completed,
            progress_pct=100,
            finished_at=datetime.now(timezone.utc),
        )
        job = store.get_job(job_id)
        result = store.job_to_dict(job) if job else {}
        result["mapping_id"] = mapping_id
        result["edge_count"] = edge_count
        result["community_count"] = comm_count
        return result

    except Exception as exc:
        store.update_job(
            job_id,
            status=JobStatus.failed,
            error_message=str(exc),
            finished_at=datetime.now(timezone.utc),
        )
        raise


def _write_batch(
    store: MemoryStore | PostgresStore,
    tenant_id: str,
    mapping_id: str,
    strategy: RulesStrategy,
    batch: list[tuple[str, str, str | None]],
) -> int:
    results = strategy.assign_batch(batch)
    for (word, text, _), res in zip(batch, results):
        store.upsert_chunk(
            tenant_id=tenant_id,
            mapping_id=mapping_id,
            chunk_ref=word,
            chunk_text=text,
            category_slug=res.category_slug,
            embedding=res.embedding,
            sem_embedding=res.sem_embedding,
        )
    return len(batch)
