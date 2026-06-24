"""Integration tests for PostgresStore (requires PRISMRAG_DB_DSN)."""
from __future__ import annotations

import os
import uuid

import pytest

from tests.conftest import HEALTHCARE_MAPPING
from tests.fixtures.lib_conftest import inline_records_from_mapping


def _pg_dsn() -> str:
    return os.getenv("PRISMRAG_DB_DSN") or os.getenv("DATABASE_URL") or ""


def _pg_available() -> bool:
    dsn = _pg_dsn()
    if not dsn:
        return False
    try:
        import psycopg2
        conn = psycopg2.connect(dsn)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_available(),
    reason="Postgres unavailable — set PRISMRAG_DB_DSN to a reachable database",
)


@pytest.fixture
def pg_tenant_id():
    return str(uuid.uuid4())


@pytest.fixture
def pg_store(pg_tenant_id):
    from prismrag_patch import PostgresStore

    store = PostgresStore(dsn=_pg_dsn())
    store.ensure_schema()
    store.ensure_tenant(pg_tenant_id, name="pytest-lib-store")
    yield store
    store.delete_tenant_data(pg_tenant_id)
    store.close()


@pytest.fixture
def pg_rag(pg_store, pg_tenant_id):
    from prismrag_patch import PrismRAG

    rag = PrismRAG(
        mapping=HEALTHCARE_MAPPING,
        tenant_id=pg_tenant_id,
        store=pg_store,
        auto_ensure_tenant=False,
    )
    rag.ingest(records=inline_records_from_mapping(HEALTHCARE_MAPPING))
    return rag


class TestPostgresStore:
    def test_ingest_writes_chunk_embedding(self, pg_rag, pg_tenant_id):
        mid = pg_rag.store.latest_mapping(pg_tenant_id)
        chunks = pg_rag.store.all_chunks(pg_tenant_id, mid)
        assert len(chunks) == len(HEALTHCARE_MAPPING["rules"])

    def test_communities_in_db(self, pg_rag, pg_tenant_id):
        mid = pg_rag.store.latest_mapping(pg_tenant_id)
        comms = pg_rag.store.list_communities(pg_tenant_id, mid)
        assert len(comms) >= 1

    def test_graph_edges_in_db(self, pg_rag, pg_tenant_id):
        mid = pg_rag.store.latest_mapping(pg_tenant_id)
        edges = pg_rag.store.get_edges(pg_tenant_id, mid)
        assert len(edges) > 0

    def test_search_from_postgres(self, pg_rag):
        data = pg_rag.search("insulin medication", top_k=5)
        assert len(data["results"]) > 0
        assert data["retrieval_mode"] in ("graph_rag", "direct")

    def test_mapping_rules_persisted(self, pg_rag, pg_tenant_id):
        mid = pg_rag.store.latest_mapping(pg_tenant_id)
        cfg = pg_rag.store.get_mapping_config(mid)
        assert len(cfg.rules) == len(HEALTHCARE_MAPPING["rules"])
        assert len(cfg.categories) == len(HEALTHCARE_MAPPING["categories"])

    def test_append_upserts_chunk(self, pg_rag):
        results = pg_rag.append_chunks(
            chunks=[{"ref": "pg_test_chunk", "text": "pg test metformin"}],
            new_rules=[{"word": "pg_test_chunk", "category_slug": "medication"}],
        )
        assert results[0]["chunk_ref"] == "pg_test_chunk"
        mid = pg_rag.store.latest_mapping(pg_rag.tenant_id)
        found = pg_rag.store.list_chunks(pg_rag.tenant_id, mid, refs=["pg_test_chunk"])
        assert len(found) == 1

    def test_chunk_quality_from_db(self, pg_rag):
        report = pg_rag.chunk_quality()
        assert report["summary"]["total"] >= len(HEALTHCARE_MAPPING["rules"])

    def test_from_postgres_factory(self, pg_tenant_id):
        from prismrag_patch import PrismRAG, PostgresStore

        dsn = _pg_dsn()
        store = PostgresStore(dsn=dsn)
        store.ensure_tenant(pg_tenant_id, "factory-test")
        try:
            rag = PrismRAG.from_postgres(
                dsn=dsn,
                mapping=HEALTHCARE_MAPPING,
                tenant_id=pg_tenant_id,
            )
            job = rag.ingest(records=inline_records_from_mapping(HEALTHCARE_MAPPING)[:3])
            assert job["status"] == "completed"
            assert job["records_written"] == 3
        finally:
            store.delete_tenant_data(pg_tenant_id)
            store.close()
