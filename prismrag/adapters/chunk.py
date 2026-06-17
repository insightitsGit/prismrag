"""PrismRAG — Chunk adapter (re-map existing pgvector store)."""
from __future__ import annotations

from typing import Iterator

from prismrag.adapters.base import Record, SourceAdapter
from prismrag.models import ChunkSourceConfig


class ChunkAdapter(SourceAdapter):
    """
    Re-map chunks from an existing pgvector table.

    Streams (word=first_token, text=chunk_text, ref=row_id) records
    so that the mapping pipeline can project them through the personal MLP.

    The source table does NOT need to use PrismRAG's schema — any table
    with a text column and an optional id column works.
    """

    def __init__(self, config: ChunkSourceConfig):
        self._config = config
        self._conn   = None

    def _open(self):
        import psycopg2
        self._conn = psycopg2.connect(self._config.source_dsn)
        return self._conn

    def count_estimate(self) -> int | None:
        try:
            conn = self._open()
            where = f"WHERE {self._config.where_clause}" if self._config.where_clause else ""
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {self._config.source_table} {where}")
            row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception:
            return None

    def stream(self) -> Iterator[Record]:
        conn = self._open()
        try:
            tcol = self._config.text_column
            rcol = self._config.ref_column
            where = f"WHERE {self._config.where_clause}" if self._config.where_clause else ""
            cur = conn.cursor("prismrag_chunk_stream", withhold=True)
            cur.itersize = 500
            cur.execute(f"SELECT {rcol}, {tcol} FROM {self._config.source_table} {where}")

            for row in cur:
                ref  = str(row[0] or "")
                text = str(row[1] or "").strip()
                if not text:
                    continue
                # Use first meaningful token as the "word" key
                tokens = [t for t in text.lower().split() if len(t) > 2]
                word   = tokens[0] if tokens else text[:40].lower()
                yield Record(word=word, text=text, ref=ref)
        finally:
            self.close()

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
