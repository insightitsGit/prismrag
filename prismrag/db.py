"""PrismRAG — database connection pool and helpers."""
from __future__ import annotations

import os
import threading
from typing import Any

_pool = None
_pool_lock = threading.Lock()
_schema_ready = False
_schema_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        from psycopg2 import pool as pg_pool
        from prismrag.config import DB_POOL_MIN, DB_POOL_MAX, DATABASE_URL
        dsn = DATABASE_URL or os.getenv("DATABASE_URL") or os.getenv("PRISMRAG_DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "PRISMRAG_DATABASE_URL environment variable is not set. "
                "Example: postgresql://user:pass@localhost:5432/prismrag"
            )
        _pool = pg_pool.ThreadedConnectionPool(DB_POOL_MIN, DB_POOL_MAX, dsn)
        return _pool


def get_conn():
    """Return a connection from the pool. Call release_conn() when done."""
    return _get_pool().getconn()


def release_conn(conn) -> None:
    """Return connection to pool. Safe to call even if conn is None."""
    if conn is None:
        return
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


def vector_to_pg(vec) -> str:
    """Convert a python list/array to pgvector literal '[x,y,...]'."""
    return '[' + ','.join(f'{float(x):.8f}' for x in vec) + ']'


def init_schema(force: bool = False) -> None:
    """Run schema.sql + HNSW index creation. Idempotent."""
    global _schema_ready
    if _schema_ready and not force:
        return
    with _schema_lock:
        if _schema_ready and not force:
            return
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, encoding='utf-8') as f:
            sql = f.read()
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
            _schema_ready = True
            print('[PrismRAG] Schema ready')
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f'PrismRAG schema init failed: {e}') from e
        finally:
            release_conn(conn)
