"""Step 5 — bridge vectors + append + quality."""
import pytest

pytest.importorskip("networkx")


class TestStep05BridgeAppend:
    def test_bridge_created(self, healthcare_rag):
        comms = healthcare_rag.list_communities()
        if len(comms) < 2:
            pytest.skip("Need at least 2 communities")
        bridge = healthcare_rag.create_bridge(
            comms[0]["community_id"],
            comms[1]["community_id"],
            bridge_label="QA Bridge: diagnosis-treatment",
        )
        assert "bridge_id" in bridge
        assert bridge["label"] == "QA Bridge: diagnosis-treatment"

    def test_bridge_searchable(self, healthcare_rag):
        comms = healthcare_rag.list_communities()
        if len(comms) < 2:
            pytest.skip("Need at least 2 communities")
        healthcare_rag.create_bridge(comms[0]["community_id"], comms[1]["community_id"])
        data = healthcare_rag.search("diagnosis and treatment pathway", top_k=10)
        categories = {res["category_slug"] for res in data["results"]}
        assert len(categories) >= 1

    def test_append_chunks(self, healthcare_rag):
        results = healthcare_rag.append_chunks(
            chunks=[{"ref": "new_symptom_xyz", "text": "new symptom chest pain fever"}],
            new_rules=[{"word": "new_symptom_xyz", "category_slug": "symptoms", "weight": 1.0}],
        )
        assert len(results) == 1
        assert results[0]["chunk_ref"] == "new_symptom_xyz"
        assert "quality_score" in results[0]
        assert 0.0 <= results[0]["quality_score"] <= 1.0

    def test_chunk_quality_summary(self, healthcare_rag):
        report = healthcare_rag.chunk_quality()
        assert report["summary"]["total"] == len(healthcare_rag.export_chunks())
        assert report["summary"]["avg_quality"] is not None
        assert 0.0 <= report["summary"]["avg_quality"] <= 1.0

    def test_append_without_mapping_fails(self):
        from prismrag_patch import PrismRAG
        from tests.conftest import HEALTHCARE_MAPPING

        rag = PrismRAG(mapping=HEALTHCARE_MAPPING, tenant_id="no-ingest")
        with pytest.raises(ValueError, match="No active mapping"):
            rag.append_chunks(chunks=[{"ref": "x", "text": "x"}])
