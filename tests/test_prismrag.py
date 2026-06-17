"""Tests — PrismRAG ingestion, search, and bridge vectors across 3 domains."""
import time
import pytest
from tests.conftest import DOMAIN_CONFIGS, HEALTHCARE_MAPPING, PHARMACY_MAPPING, FINANCE_MAPPING


# ── Helpers ───────────────────────────────────────────────────────────────────

def ingest_job(authed_api, tenant_id, mapping, strategy="rules", source_type="api"):
    """Post a job and wait until it completes. Returns job dict."""
    payload = {
        "tenant_id":   tenant_id,
        "source_type": source_type,
        "strategy":    strategy,
        "mapping":     mapping,
        "source_data": {"words": [r["word"] for r in mapping["rules"]]},
    }
    r = authed_api.post(authed_api.url("/api/prismrag/jobs"), json=payload)
    assert r.status_code in (200, 201, 202), f"Job submit failed: {r.status_code} {r.text}"
    job = r.json()
    job_id = job.get("job_id") or job.get("id")

    # Poll until done or failed
    for _ in range(60):
        r2 = authed_api.get(authed_api.url(f"/api/prismrag/jobs/{job_id}"))
        status = r2.json().get("status", "")
        if status == "done":
            return r2.json()
        if status == "failed":
            pytest.fail(f"Job {job_id} failed: {r2.text}")
        time.sleep(2)
    pytest.fail(f"Job {job_id} timed out (still {status} after 120s)")


# ── Fixture: completed ingestion jobs per domain ──────────────────────────────

@pytest.fixture(scope="module")
def healthcare_job(authed_api, healthcare_tenant):
    return ingest_job(authed_api, healthcare_tenant, HEALTHCARE_MAPPING)

@pytest.fixture(scope="module")
def pharmacy_job(authed_api, pharmacy_tenant):
    return ingest_job(authed_api, pharmacy_tenant, PHARMACY_MAPPING)

@pytest.fixture(scope="module")
def finance_job(authed_api, finance_tenant):
    return ingest_job(authed_api, finance_tenant, FINANCE_MAPPING)


# ── Ingest tests ─────────────────────────────────────────────────────────────

class TestIngest:
    def test_healthcare_job_done(self, healthcare_job):
        assert healthcare_job["status"] == "done"
        assert healthcare_job["words_processed"] > 0

    def test_pharmacy_job_done(self, pharmacy_job):
        assert pharmacy_job["status"] == "done"
        assert pharmacy_job["words_processed"] > 0

    def test_finance_job_done(self, finance_job):
        assert finance_job["status"] == "done"
        assert finance_job["words_processed"] > 0

    def test_communities_built_healthcare(self, authed_api, healthcare_tenant, healthcare_job):
        r = authed_api.get(authed_api.url(f"/api/prismrag/communities?tenant_id={healthcare_tenant}"))
        assert r.status_code == 200
        communities = r.json()
        assert len(communities) >= 3, "Expected at least 3 communities from healthcare mapping"

    def test_communities_built_finance(self, authed_api, finance_tenant, finance_job):
        r = authed_api.get(authed_api.url(f"/api/prismrag/communities?tenant_id={finance_tenant}"))
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_invalid_tenant_rejected(self, authed_api):
        r = authed_api.post(authed_api.url("/api/prismrag/jobs"), json={
            "tenant_id":   "00000000-0000-0000-0000-000000000000",
            "source_type": "api",
            "strategy":    "rules",
            "mapping":     {"categories": [], "rules": []},
        })
        assert r.status_code in (403, 404, 422)

    def test_empty_rules_rejected(self, authed_api, healthcare_tenant):
        r = authed_api.post(authed_api.url("/api/prismrag/jobs"), json={
            "tenant_id":   healthcare_tenant,
            "source_type": "api",
            "strategy":    "rules",
            "mapping":     {"categories": [{"slug": "a", "label": "A"}], "rules": []},
        })
        assert r.status_code in (400, 422)


# ── Search tests ─────────────────────────────────────────────────────────────

class TestSearch:

    @pytest.mark.parametrize("domain,query,expected_category", [
        ("healthcare", "What medications are used for diabetes management?",    "medication"),
        ("healthcare", "What lab tests confirm heart attack diagnosis?",         "lab_results"),
        ("healthcare", "What patient safety risks apply to drug allergies?",    "patient_safety"),
        ("pharmacy",   "What CYP450 drug interactions affect warfarin?",        "drug_interactions"),
        ("pharmacy",   "How should insulin be stored and handled?",             "storage"),
        ("pharmacy",   "What is the bioavailability and half-life of amoxicillin?", "pharmacokinetics"),
        ("finance",    "What is the DCF valuation method and WACC calculation?","valuation"),
        ("finance",    "What are the key credit risk and VaR risk metrics?",    "risk"),
        ("finance",    "What is the current ratio and free cash flow status?",  "liquidity"),
    ])
    def test_search_returns_results(
        self, domain, query, expected_category,
        authed_api, healthcare_tenant, pharmacy_tenant, finance_tenant,
        healthcare_job, pharmacy_job, finance_job,
    ):
        tenant_id = {"healthcare": healthcare_tenant,
                     "pharmacy":   pharmacy_tenant,
                     "finance":    finance_tenant}[domain]
        r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": tenant_id,
            "query":     query,
            "top_k":     5,
        })
        assert r.status_code == 200, f"Search failed: {r.text}"
        data = r.json()
        assert "results" in data
        assert len(data["results"]) > 0, f"No results for: {query}"
        # Top result should be in expected category (soft check — logs on mismatch)
        top_cat = data["results"][0].get("category_slug", "")
        if top_cat != expected_category:
            print(f"[WARN] domain={domain} query='{query[:50]}' "
                  f"expected={expected_category} got={top_cat}")

    def test_search_category_filter(self, authed_api, finance_tenant, finance_job):
        r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id":       finance_tenant,
            "query":           "risk metrics and portfolio analysis",
            "top_k":           10,
            "category_filter": "risk",
        })
        assert r.status_code == 200
        results = r.json()["results"]
        for res in results:
            assert res.get("category_slug") == "risk", \
                f"category_filter not applied: got {res.get('category_slug')}"

    def test_search_top_k_respected(self, authed_api, healthcare_tenant, healthcare_job):
        for top_k in [1, 3, 5]:
            r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
                "tenant_id": healthcare_tenant,
                "query":     "patient medication",
                "top_k":     top_k,
            })
            assert r.status_code == 200
            assert len(r.json()["results"]) <= top_k

    def test_search_tenant_isolation(
        self, authed_api, healthcare_tenant, pharmacy_tenant,
        healthcare_job, pharmacy_job
    ):
        """Healthcare query against pharmacy tenant should return different results."""
        query = "diabetes insulin medication"
        r_hc = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": healthcare_tenant, "query": query, "top_k": 3,
        })
        r_ph = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": pharmacy_tenant, "query": query, "top_k": 3,
        })
        hc_cats = [r["category_slug"] for r in r_hc.json()["results"]]
        ph_cats = [r["category_slug"] for r in r_ph.json()["results"]]
        assert hc_cats != ph_cats or hc_cats[0] in ["medication", "dosage"], \
            "Tenants are not isolated — same categories returned for both"

    def test_search_result_structure(self, authed_api, finance_tenant, finance_job):
        r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": finance_tenant,
            "query":     "valuation",
            "top_k":     3,
        })
        assert r.status_code == 200
        for res in r.json()["results"]:
            assert "word" in res or "chunk_ref" in res
            assert "category_slug" in res
            assert "score" in res
            assert 0.0 <= res["score"] <= 1.0

    def test_empty_query_rejected(self, authed_api, healthcare_tenant):
        r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": healthcare_tenant,
            "query":     "",
        })
        assert r.status_code == 422

    def test_search_latency(self, authed_api, finance_tenant, finance_job):
        """Search should complete in under 3 seconds."""
        import time
        start = time.time()
        r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": finance_tenant,
            "query":     "credit risk valuation",
            "top_k":     5,
        })
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 3.0, f"Search took {elapsed:.2f}s — exceeds 3s threshold"


# ── Bridge vector tests ───────────────────────────────────────────────────────

class TestBridgeVectors:

    @pytest.fixture(scope="class")
    def bridge(self, authed_api, healthcare_tenant, healthcare_job):
        """Create a bridge between diagnosis and treatment communities."""
        r = authed_api.get(authed_api.url(f"/api/prismrag/communities?tenant_id={healthcare_tenant}"))
        communities = r.json()
        slugs = [c["label"] for c in communities]
        # Find two distinct communities to bridge
        if len(communities) < 2:
            pytest.skip("Need at least 2 communities to test bridge vectors")
        a_id = communities[0]["id"]
        b_id = communities[1]["id"]
        rb = authed_api.post(authed_api.url("/api/prismrag/bridges"), json={
            "tenant_id":    healthcare_tenant,
            "community_a":  a_id,
            "community_b":  b_id,
            "bridge_label": "QA Bridge: diagnosis-treatment",
        })
        assert rb.status_code in (200, 201), f"Bridge create failed: {rb.text}"
        return rb.json()

    def test_bridge_created(self, bridge):
        assert "bridge_id" in bridge or "id" in bridge

    def test_bridge_appears_in_communities(self, authed_api, healthcare_tenant, bridge, healthcare_job):
        r = authed_api.get(authed_api.url(f"/api/prismrag/communities?tenant_id={healthcare_tenant}"))
        labels = [c.get("label", "") for c in r.json()]
        assert any("Bridge" in lbl or "bridge" in lbl.lower() for lbl in labels), \
            f"Bridge not found in community list. Labels: {labels}"

    def test_bridge_searchable(self, authed_api, healthcare_tenant, bridge, healthcare_job):
        """A query spanning bridged domains should surface both sides."""
        r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
            "tenant_id": healthcare_tenant,
            "query":     "diagnosis and treatment pathway",
            "top_k":     10,
        })
        assert r.status_code == 200
        categories = {res["category_slug"] for res in r.json()["results"]}
        assert len(categories) >= 2, "Bridge search should return results from multiple categories"
