"""
PrismRAG — Nightly cleanup worker.

Deletes expired rows from:
  - api_request_log   (plan-based TTL: free=7d, starter/pro=30d, enterprise=90d)
  - search_result_log (expires_at column)
  - ingest_result_log (expires_at column)
  - large_file_upload (pending_upload older than 24h — SAS expired)

Run via cron (Azure Container Apps job) or directly:
  python -m prismrag.worker.cleanup
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Per-plan log retention in days
RETENTION_DAYS = {
    "free":         7,
    "starter":      30,
    "professional": 30,
    "enterprise":   90,
}


def run_cleanup() -> dict[str, int]:
    from prismrag.db import get_conn, release_conn
    conn = get_conn()
    deleted: dict[str, int] = {}
    try:
        cur = conn.cursor()

        # 1. api_request_log — join to user_account for plan-based retention
        #    Users with no account (anonymous, API key unknown) get free-tier TTL (7d)
        cur.execute("""
            DELETE FROM prismrag.api_request_log
            WHERE created_at < now() - INTERVAL '1 day' *
                COALESCE(
                    (
                        SELECT CASE u.plan
                            WHEN 'enterprise'    THEN 90
                            WHEN 'professional'  THEN 30
                            WHEN 'starter'       THEN 30
                            ELSE 7
                        END
                        FROM prismrag.user_account u
                        WHERE u.id::text = api_request_log.user_id
                        LIMIT 1
                    ),
                    7  -- anonymous / API key users
                )
        """)
        deleted["api_request_log"] = cur.rowcount

        # 2. search_result_log — simple expires_at column
        cur.execute("""
            DELETE FROM prismrag.search_result_log
            WHERE expires_at < now()
        """)
        deleted["search_result_log"] = cur.rowcount

        # 3. ingest_result_log
        cur.execute("""
            DELETE FROM prismrag.ingest_result_log
            WHERE expires_at < now()
        """)
        deleted["ingest_result_log"] = cur.rowcount

        # 4. large_file_upload — stale pending uploads (SAS token expired > 24h ago)
        cur.execute("""
            DELETE FROM prismrag.large_file_upload
            WHERE status = 'pending_upload'
              AND created_at < now() - INTERVAL '24 hours'
        """)
        deleted["large_file_upload_stale"] = cur.rowcount

        conn.commit()
        log.info("Cleanup complete: %s", deleted)
        return deleted
    except Exception as exc:
        conn.rollback()
        log.error("Cleanup failed: %s", exc)
        raise
    finally:
        release_conn(conn)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_cleanup()
    print("Deleted rows:", result)
