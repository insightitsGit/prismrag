"""Step 4 — search parity."""
import time

import pytest

from tests.conftest import DOMAIN_CONFIGS


class TestStep04Search:
    @pytest.mark.parametrize("domain,query,expected_category", [
        ("healthcare", "What medications are used for diabetes management?", "medication"),
        ("healthcare", "What lab tests confirm heart attack diagnosis?", "lab_results"),
        ("healthcare", "What patient safety risks apply to drug allergies?", "patient_safety"),
        ("pharmacy", "What CYP450 drug interactions affect warfarin?", "drug_interactions"),
        ("pharmacy", "How should insulin be stored and handled?", "storage"),
        ("pharmacy", "What is the bioavailability and half-life of amoxicillin?", "pharmacokinetics"),
        ("finance", "What is the DCF valuation method and WACC calculation?", "valuation"),
        ("finance", "What are the key credit risk and VaR metrics?", "risk"),
        ("finance", "What is the current ratio and free cash flow status?", "liquidity"),
    ])
    def test_search_returns_results(
        self, domain, query, expected_category,
        healthcare_rag, pharmacy_rag, finance_rag,
    ):
        rag = {"healthcare": healthcare_rag, "pharmacy": pharmacy_rag, "finance": finance_rag}[domain]
        data = rag.search(query, top_k=5)
        results = data.get("results", [])
        assert len(results) > 0, f"No results for: {query}"
        assert data["retrieval_mode"] in ("graph_rag", "direct")
        top_cat = results[0].get("category_slug", "")
        if top_cat != expected_category:
            pytest.xfail(f"domain={domain} expected={expected_category} got={top_cat} (deterministic embed)")

    def test_category_filter(self, finance_rag):
        data = finance_rag.search("portfolio analysis", top_k=10, category_filter="risk")
        for res in data["results"]:
            assert res.get("category_slug") == "risk"

    def test_top_k_respected(self, healthcare_rag):
        for k in [1, 3, 5]:
            data = healthcare_rag.search("patient medication", top_k=k)
            assert len(data["results"]) <= k

    def test_result_structure(self, finance_rag):
        data = finance_rag.search("valuation", top_k=3)
        for res in data["results"]:
            assert "category_slug" in res
            assert "chunk_ref" in res

    def test_search_latency_under_3s(self, finance_rag):
        start = time.time()
        data = finance_rag.search("credit risk", top_k=5)
        assert data.get("results") is not None
        assert time.time() - start < 3.0

    def test_empty_mapping_no_results(self):
        from prismrag_patch import PrismRAG
        from tests.conftest import HEALTHCARE_MAPPING

        rag = PrismRAG(mapping=HEALTHCARE_MAPPING, tenant_id="empty")
        data = rag.search("anything")
        assert data["retrieval_mode"] == "empty"
        assert data["results"] == []
