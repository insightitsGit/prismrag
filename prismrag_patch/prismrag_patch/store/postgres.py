"""PostgreSQL store — full parity with SaaS prismrag schema tables."""
from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from prismrag_patch.models import JobStatus, MappingConfig
from prismrag_patch.store.pgutil import parse_vector, vector_to_pg
from prismrag_patch.store.types import (
    BridgeRecord,
    ChunkRecord,
    CommunitySummary,
    GraphEdge,
    JobRecord,
)

logger = logging.getLogger(__name__)


class PostgresStore:
    """
    Production store backed by ``prismrag.*`` Postgres tables (see ``prismrag/schema.sql``).

    Parameters
    ----------
    dsn :
        PostgreSQL connection string. Defaults to ``PRISMRAG_DB_DSN`` env var.
    connection :
        Existing psycopg2 connection (caller manages lifecycle). If set, ``dsn`` is ignored.
    """

    def __init__(self, dsn: str | None = None, connection: Any | None = None) -> None:
        self._dsn = dsn or os.getenv("PRISMRAG_DB_DSN") or os.getenv("DATABASE_URL") or ""
        self._conn = connection
        self._owned = connection is None

    @contextmanager
    def _borrow(self) -> Iterator[Any]:
        if self._conn is not None:
            yield self._conn
            return
        if not self._dsn:
            raise RuntimeError(
                "PostgresStore requires dsn= or PRISMRAG_DB_DSN / DATABASE_URL env var"
            )
        import psycopg2
        conn = psycopg2.connect(self._dsn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self) -> None:
        if self._owned and self._conn is not None:
            self._conn.close()
            self._conn = None

    def ensure_tenant(self, tenant_id: str, name: str | None = None) -> None:
        """Insert tenant row if missing (required FK for all RAG tables)."""
        label = name or f"tenant-{tenant_id[:8]}"
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO prismrag.tenant (id, name)
                VALUES (%s::uuid, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (tenant_id, label),
            )

    def ensure_schema(self) -> None:
        """Run core RAG schema if tables are missing (requires schema.sql on disk)."""
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'prismrag' AND table_name = 'chunk_embedding'"
            )
            if cur.fetchone():
                return
        raise RuntimeError(
            "prismrag schema not found. Run prismrag/schema.sql against your database first."
        )

    # ── Mapping ───────────────────────────────────────────────────────────────

    def persist_mapping(
        self, tenant_id: str, mapping: MappingConfig, strategy: str = "rules"
    ) -> str:
        mapping_id = str(uuid.uuid4())
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM prismrag.tenant WHERE id = %s::uuid FOR UPDATE", (tenant_id,))
            if not cur.fetchone():
                raise ValueError(f"Tenant {tenant_id} not found — call ensure_tenant() first")

            cur.execute(
                "UPDATE prismrag.mapping_version SET status = 'archived' "
                "WHERE tenant_id = %s::uuid AND status = 'active'",
                (tenant_id,),
            )
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM prismrag.mapping_version "
                "WHERE tenant_id = %s::uuid",
                (tenant_id,),
            )
            next_version = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO prismrag.mapping_version
                    (id, tenant_id, version, strategy, status, config_json)
                VALUES (%s::uuid, %s::uuid, %s, %s, 'active', %s::jsonb)
                RETURNING id
                """,
                (mapping_id, tenant_id, next_version, strategy, json.dumps({})),
            )
            row = cur.fetchone()
            if row:
                mapping_id = str(row[0])

            for i, cat in enumerate(mapping.categories):
                cur.execute(
                    """
                    INSERT INTO prismrag.mapping_category
                        (mapping_id, category_slug, category_label, sort_order)
                    VALUES (%s::uuid, %s, %s, %s)
                    ON CONFLICT (mapping_id, category_slug) DO NOTHING
                    """,
                    (mapping_id, cat["slug"], cat["label"], cat.get("sort_order", i)),
                )
            for rule in mapping.rules:
                cur.execute(
                    """
                    INSERT INTO prismrag.mapping_rule
                        (mapping_id, word, category_slug, weight, source)
                    VALUES (%s::uuid, %s, %s, %s, 'intake')
                    ON CONFLICT (mapping_id, word) DO UPDATE
                    SET category_slug = EXCLUDED.category_slug,
                        weight = EXCLUDED.weight
                    """,
                    (
                        mapping_id,
                        rule["word"].strip().lower(),
                        rule["category_slug"],
                        float(rule.get("weight", 1.0)),
                    ),
                )
        return mapping_id

    def latest_mapping(self, tenant_id: str) -> str | None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id::text FROM prismrag.mapping_version
                WHERE tenant_id = %s::uuid AND status = 'active'
                ORDER BY version DESC LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None

    def get_mapping_config(self, mapping_id: str) -> MappingConfig | None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT category_slug, category_label, sort_order
                FROM prismrag.mapping_category
                WHERE mapping_id = %s::uuid
                ORDER BY sort_order
                """,
                (mapping_id,),
            )
            cats = [
                {"slug": r[0], "label": r[1], "sort_order": r[2]}
                for r in cur.fetchall()
            ]
            if not cats:
                return None
            cur.execute(
                """
                SELECT word, category_slug, weight
                FROM prismrag.mapping_rule
                WHERE mapping_id = %s::uuid
                ORDER BY word
                """,
                (mapping_id,),
            )
            rules = [
                {"word": r[0], "category_slug": r[1], "weight": float(r[2])}
                for r in cur.fetchall()
            ]
            return MappingConfig(categories=cats, rules=rules)

    def merge_rules(self, mapping_id: str, new_rules: list[dict[str, Any]]) -> MappingConfig:
        with self._borrow() as conn:
            cur = conn.cursor()
            for rule in new_rules:
                cur.execute(
                    """
                    INSERT INTO prismrag.mapping_rule
                        (mapping_id, word, category_slug, weight, source)
                    VALUES (%s::uuid, %s, %s, %s, 'append')
                    ON CONFLICT (mapping_id, word) DO UPDATE
                    SET category_slug = EXCLUDED.category_slug,
                        weight = EXCLUDED.weight
                    """,
                    (
                        mapping_id,
                        rule["word"].strip().lower(),
                        rule["category_slug"],
                        float(rule.get("weight", 1.0)),
                    ),
                )
        cfg = self.get_mapping_config(mapping_id)
        if cfg is None:
            raise ValueError(f"Mapping {mapping_id} not found")
        return cfg

    # ── Chunks ────────────────────────────────────────────────────────────────

    def upsert_chunk(
        self,
        tenant_id: str,
        mapping_id: str,
        chunk_ref: str,
        chunk_text: str,
        category_slug: str,
        embedding: Any,
        sem_embedding: Any,
        community_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        meta = json.dumps(metadata or {})
        sem_pg = vector_to_pg(sem_embedding) if sem_embedding is not None else None
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO prismrag.chunk_embedding
                    (tenant_id, mapping_id, chunk_text, chunk_ref, category_slug,
                     community_id, embedding, sem_embedding, metadata_json)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::vector, %s::vector, %s::jsonb)
                ON CONFLICT (tenant_id, mapping_id, chunk_ref) DO UPDATE SET
                    chunk_text    = EXCLUDED.chunk_text,
                    category_slug = EXCLUDED.category_slug,
                    community_id  = COALESCE(EXCLUDED.community_id, prismrag.chunk_embedding.community_id),
                    embedding     = EXCLUDED.embedding,
                    sem_embedding = EXCLUDED.sem_embedding,
                    metadata_json = EXCLUDED.metadata_json
                """,
                (
                    tenant_id, mapping_id, chunk_text, chunk_ref, category_slug,
                    community_id,
                    vector_to_pg(embedding),
                    sem_pg,
                    meta,
                ),
            )

    def list_chunks(
        self,
        tenant_id: str,
        mapping_id: str,
        refs: list[str] | None = None,
        category_filter: str | None = None,
    ) -> list[ChunkRecord]:
        sql = """
            SELECT chunk_ref, chunk_text, category_slug, community_id,
                   embedding::text, sem_embedding::text, metadata_json
            FROM prismrag.chunk_embedding
            WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid
        """
        params: list[Any] = [tenant_id, mapping_id]
        if refs is not None:
            sql += " AND chunk_ref = ANY(%s)"
            params.append(refs)
        if category_filter:
            sql += " AND category_slug = %s"
            params.append(category_filter)
        sql += " ORDER BY chunk_ref"

        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()

        out: list[ChunkRecord] = []
        for row in rows:
            emb = parse_vector(row[4])
            sem = parse_vector(row[5])
            if emb is None or sem is None:
                continue
            meta = row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}")
            out.append(ChunkRecord(
                chunk_ref=row[0],
                chunk_text=row[1],
                category_slug=row[2],
                embedding=emb,
                sem_embedding=sem,
                community_id=row[3],
                metadata=meta,
            ))
        return out

    def all_chunks(self, tenant_id: str, mapping_id: str) -> list[ChunkRecord]:
        return self.list_chunks(tenant_id, mapping_id)

    # ── Graph ─────────────────────────────────────────────────────────────────

    def set_edges(self, tenant_id: str, mapping_id: str, edges: list[GraphEdge]) -> None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM prismrag.word_graph_edge "
                "WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid",
                (tenant_id, mapping_id),
            )
            for e in edges:
                cur.execute(
                    """
                    INSERT INTO prismrag.word_graph_edge
                        (tenant_id, mapping_id, from_word, to_word, edge_type, weight)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, mapping_id, from_word, to_word, edge_type) DO NOTHING
                    """,
                    (tenant_id, mapping_id, e.from_word, e.to_word, e.edge_type, e.weight),
                )

    def get_edges(self, tenant_id: str, mapping_id: str) -> list[GraphEdge]:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT from_word, to_word, edge_type, weight
                FROM prismrag.word_graph_edge
                WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid
                """,
                (tenant_id, mapping_id),
            )
            rows = cur.fetchall()
        return [GraphEdge(r[0], r[1], r[2], float(r[3])) for r in rows]

    def add_edge(
        self,
        tenant_id: str,
        mapping_id: str,
        from_word: str,
        to_word: str,
        edge_type: str,
        weight: float,
    ) -> None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO prismrag.word_graph_edge
                    (tenant_id, mapping_id, from_word, to_word, edge_type, weight)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, mapping_id, from_word, to_word, edge_type) DO NOTHING
                """,
                (tenant_id, mapping_id, from_word, to_word, edge_type, weight),
            )

    # ── Communities ───────────────────────────────────────────────────────────

    def set_communities(
        self,
        tenant_id: str,
        mapping_id: str,
        summaries: list[CommunitySummary],
        members: dict[str, int],
    ) -> None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM prismrag.community_member "
                "WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid",
                (tenant_id, mapping_id),
            )
            cur.execute(
                "DELETE FROM prismrag.community_summary "
                "WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid",
                (tenant_id, mapping_id),
            )

            for s in summaries:
                centroid_pg = vector_to_pg(s.centroid_vec) if s.centroid_vec is not None else None
                cur.execute(
                    """
                    INSERT INTO prismrag.community_summary
                        (tenant_id, mapping_id, community_id, label, summary_text,
                         top_words, word_count, centroid_vec)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (tenant_id, mapping_id, community_id) DO UPDATE
                    SET label = EXCLUDED.label,
                        summary_text = EXCLUDED.summary_text,
                        top_words = EXCLUDED.top_words,
                        word_count = EXCLUDED.word_count,
                        centroid_vec = EXCLUDED.centroid_vec
                    """,
                    (
                        tenant_id, mapping_id, s.community_id, s.label, s.summary_text,
                        s.top_words, s.word_count, centroid_pg,
                    ),
                )

            for word, cid in members.items():
                cur.execute(
                    """
                    INSERT INTO prismrag.community_member
                        (tenant_id, mapping_id, word, community_id)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    ON CONFLICT (tenant_id, mapping_id, word) DO UPDATE
                    SET community_id = EXCLUDED.community_id
                    """,
                    (tenant_id, mapping_id, word, cid),
                )

            for word, cid in members.items():
                cur.execute(
                    """
                    UPDATE prismrag.chunk_embedding
                    SET community_id = %s
                    WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid AND chunk_ref = %s
                    """,
                    (cid, tenant_id, mapping_id, word),
                )

    def list_communities(self, tenant_id: str, mapping_id: str) -> list[CommunitySummary]:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT community_id, label, summary_text, top_words, word_count,
                       centroid_vec::text
                FROM prismrag.community_summary
                WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid
                ORDER BY word_count DESC
                """,
                (tenant_id, mapping_id),
            )
            rows = cur.fetchall()
        return [
            CommunitySummary(
                community_id=r[0],
                label=r[1],
                summary_text=r[2],
                top_words=list(r[3] or []),
                word_count=r[4],
                centroid_vec=parse_vector(r[5]),
            )
            for r in rows
        ]

    def get_community(
        self, tenant_id: str, mapping_id: str, community_id: int
    ) -> CommunitySummary | None:
        comms = self.list_communities(tenant_id, mapping_id)
        return next((c for c in comms if c.community_id == community_id), None)

    # ── Bridges ───────────────────────────────────────────────────────────────

    def upsert_bridge(
        self,
        tenant_id: str,
        mapping_id: str,
        community_a: int,
        community_b: int,
        label: str,
        embedding: Any,
        sem_embedding: Any,
    ) -> BridgeRecord:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO prismrag.bridge_vector
                    (tenant_id, mapping_id, community_a, community_b, label,
                     embedding, sem_embedding)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::vector, %s::vector)
                ON CONFLICT (tenant_id, mapping_id, community_a, community_b) DO UPDATE
                SET label = EXCLUDED.label,
                    embedding = EXCLUDED.embedding,
                    sem_embedding = EXCLUDED.sem_embedding
                RETURNING id
                """,
                (
                    tenant_id, mapping_id, community_a, community_b, label,
                    vector_to_pg(embedding),
                    vector_to_pg(sem_embedding),
                ),
            )
            bridge_id = int(cur.fetchone()[0])
        import numpy as np
        return BridgeRecord(
            bridge_id=bridge_id,
            community_a=community_a,
            community_b=community_b,
            label=label,
            embedding=np.asarray(embedding, dtype=float),
            sem_embedding=np.asarray(sem_embedding, dtype=float),
        )

    def list_bridges(self, tenant_id: str, mapping_id: str) -> list[BridgeRecord]:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, community_a, community_b, label,
                       embedding::text, sem_embedding::text
                FROM prismrag.bridge_vector
                WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid
                """,
                (tenant_id, mapping_id),
            )
            rows = cur.fetchall()
        out: list[BridgeRecord] = []
        for r in rows:
            emb = parse_vector(r[4])
            sem = parse_vector(r[5])
            if emb is None or sem is None:
                continue
            out.append(BridgeRecord(r[0], r[1], r[2], r[3], emb, sem))
        return out

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def create_job(self, tenant_id: str, source_type: str) -> str:
        job_id = str(uuid.uuid4())
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO prismrag.ingest_job
                    (id, tenant_id, source_type, source_config, status,
                     timeout_at, created_at)
                VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, 'queued',
                        now() + interval '7200 seconds', now())
                """,
                (job_id, tenant_id, source_type, json.dumps({"source_type": source_type})),
            )
        return job_id

    def update_job(self, job_id: str, **fields: Any) -> None:
        allowed = {
            "status", "records_total", "records_written", "progress_pct",
            "error_message", "started_at", "finished_at", "mapping_id",
        }
        sets: list[str] = []
        vals: list[Any] = []
        for key, val in fields.items():
            if key not in allowed:
                continue
            col = key
            if key == "status" and isinstance(val, JobStatus):
                val = val.value
            if key == "mapping_id" and val is not None:
                sets.append(f"{col} = %s::uuid")
                vals.append(val)
                continue
            sets.append(f"{col} = %s")
            vals.append(val)
        if not sets:
            return
        vals.append(job_id)
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE prismrag.ingest_job SET {', '.join(sets)} WHERE id = %s::uuid",
                vals,
            )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id::text, tenant_id::text, status, source_type,
                       mapping_id::text, records_total, records_written,
                       progress_pct, error_message, started_at, finished_at
                FROM prismrag.ingest_job WHERE id = %s::uuid
                """,
                (job_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return JobRecord(
            job_id=row[0],
            tenant_id=row[1],
            status=JobStatus(row[2]),
            source_type=row[3],
            mapping_id=row[4],
            records_total=row[5] or 0,
            records_written=row[6] or 0,
            progress_pct=row[7] or 0,
            error_message=row[8],
            started_at=row[9],
            finished_at=row[10],
        )

    def job_to_dict(self, job: JobRecord) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "status": job.status.value,
            "source_type": job.source_type,
            "mapping_id": job.mapping_id,
            "records_total": job.records_total,
            "records_written": job.records_written,
            "progress_pct": job.progress_pct,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

    # ── MLP ───────────────────────────────────────────────────────────────────

    def save_mlp(self, tenant_id: str, mapping_id: str, blob: bytes) -> None:
        from psycopg2 import Binary
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO prismrag.mlp_artifact
                    (tenant_id, mapping_id, weights_blob, embed_dim)
                VALUES (%s::uuid, %s::uuid, %s, 256)
                ON CONFLICT (tenant_id, mapping_id) DO UPDATE
                SET weights_blob = EXCLUDED.weights_blob,
                    trained_at = now()
                """,
                (tenant_id, mapping_id, Binary(blob)),
            )

    def load_mlp(self, tenant_id: str, mapping_id: str) -> bytes | None:
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT weights_blob FROM prismrag.mlp_artifact
                WHERE tenant_id = %s::uuid AND mapping_id = %s::uuid
                """,
                (tenant_id, mapping_id),
            )
            row = cur.fetchone()
        return bytes(row[0]) if row else None

    def delete_tenant_data(self, tenant_id: str) -> None:
        """Remove all RAG data for a tenant (for tests). CASCADE handles children."""
        with self._borrow() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM prismrag.tenant WHERE id = %s::uuid", (tenant_id,))
