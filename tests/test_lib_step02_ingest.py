"""Step 2 — ingest pipeline."""
import pytest

from prismrag_patch import PrismRAG
from tests.conftest import HEALTHCARE_MAPPING, PHARMACY_MAPPING, FINANCE_MAPPING
from tests.fixtures.lib_conftest import inline_records_from_mapping


class TestStep02Ingest:
    def test_ingest_completes(self, healthcare_mapping):
        rag = PrismRAG(mapping=healthcare_mapping, tenant_id="ingest-1")
        job = rag.ingest(records=inline_records_from_mapping(healthcare_mapping))
        assert job["status"] == "completed"
        assert job["records_written"] == len(healthcare_mapping["rules"])
        assert job.get("community_count", 0) >= 1
        assert job.get("edge_count", 0) >= 1

    def test_empty_rules_rejected(self, healthcare_mapping):
        bad = {"categories": healthcare_mapping["categories"], "rules": []}
        rag = PrismRAG(mapping=bad, tenant_id="ingest-bad")
        with pytest.raises(ValueError, match="at least one rule"):
            rag.ingest(records=[{"word": "test", "text": "test"}])

    def test_three_domain_ingest(self):
        for name, mapping in [
            ("hc", HEALTHCARE_MAPPING),
            ("ph", PHARMACY_MAPPING),
            ("fi", FINANCE_MAPPING),
        ]:
            rag = PrismRAG(mapping=mapping, tenant_id=f"ingest-{name}")
            job = rag.ingest(records=inline_records_from_mapping(mapping))
            assert job["status"] == "completed", name
            assert job["records_written"] > 0, name

    def test_export_chunks_dual_vectors(self, healthcare_rag):
        chunks = healthcare_rag.export_chunks()
        assert len(chunks) == len(HEALTHCARE_MAPPING["rules"])
        c0 = chunks[0]
        assert len(c0["embedding"]) == 256
        assert len(c0["sem_embedding"]) == 768
        assert c0["category_slug"] in {c["slug"] for c in HEALTHCARE_MAPPING["categories"]}

    def test_job_tracking(self, healthcare_mapping):
        rag = PrismRAG(mapping=healthcare_mapping, tenant_id="job-track")
        job = rag.ingest(records=inline_records_from_mapping(healthcare_mapping)[:3])
        fetched = rag.get_job(job["job_id"])
        assert fetched["status"] == "completed"
        assert fetched["records_written"] == 3
