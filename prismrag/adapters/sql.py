"""PrismRAG — SQL adapter (PostgreSQL / any SQLAlchemy-compatible DB)."""
from __future__ import annotations

from typing import Iterator

from prismrag.adapters.base import Record, SourceAdapter
from prismrag.models import SQLSourceConfig


class SQLAdapter(SourceAdapter):
    """
    Stream records from an arbitrary SQL query.

    The query must return at minimum (word, text) columns.
    Large result sets are streamed via server-side cursor to avoid
    loading everything into memory.
    """

    def __init__(self, config: SQLSourceConfig):
        self._config = config
        self._conn = None

    def _open(self):
        import psycopg2
        self._conn = psycopg2.connect(self._config.connection_string)
        return self._conn

    def count_estimate(self) -> int | None:
        try:
            conn = self._open()
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM ({self._config.query}) _q")
            row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception:
            return None

    def stream(self) -> Iterator[Record]:
        conn = self._open()
        try:
            # Named cursor = server-side streaming
            cur = conn.cursor("prismrag_stream", withhold=True)
            cur.itersize = self._config.page_size
            cur.execute(self._config.query)

            wcol = self._config.word_column
            tcol = self._config.text_column
            col_names = [d[0] for d in cur.description]

            for row in cur:
                row_dict = dict(zip(col_names, row))
                word = str(row_dict.get(wcol) or "").strip().lower()
                text = str(row_dict.get(tcol) or "").strip()
                if not word:
                    continue
                if not text:
                    text = word
                ref = str(row_dict.get("id") or row_dict.get("ref") or "")
                yield Record(
                    word=word,
                    text=text,
                    ref=ref,
                    metadata={k: v for k, v in row_dict.items() if k not in (wcol, tcol)},
                )
        finally:
            self.close()

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
