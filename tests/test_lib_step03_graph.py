"""Step 3 — graph + communities."""
import pytest

pytest.importorskip("networkx")
pytest.importorskip("community")

from tests.conftest import HEALTHCARE_MAPPING, FINANCE_MAPPING


class TestStep03Graph:
    def test_communities_built_healthcare(self, healthcare_rag):
        comms = healthcare_rag.list_communities()
        assert len(comms) >= 1
        for c in comms:
            assert "label" in c
            assert "top_words" in c
            assert c["word_count"] >= 1

    def test_communities_built_finance(self, finance_rag):
        comms = finance_rag.list_communities()
        assert len(comms) >= 1

    def test_graph_edges_exist(self, healthcare_rag):
        mid = healthcare_rag.store.latest_mapping(healthcare_rag.tenant_id)
        edges = healthcare_rag.store.get_edges(healthcare_rag.tenant_id, mid)
        rule_edges = [e for e in edges if e.edge_type == "rule"]
        assert len(rule_edges) > 0

    def test_tenant_isolation(self, healthcare_rag, finance_rag):
        hc = healthcare_rag.list_communities()
        fi = finance_rag.list_communities()
        hc_labels = {c["label"] for c in hc}
        fi_labels = {c["label"] for c in fi}
        assert hc_labels != fi_labels or hc[0]["top_words"] != fi[0]["top_words"]
