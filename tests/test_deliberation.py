"""Tests — Deliberation API across 3 domain scenarios."""
import time
import pytest


DELIBERATION_QUESTIONS = [
    {
        "id": "healthcare-ma",
        "domain": "healthcare",
        "question": "What are the clinical risks and treatment protocols when a patient with diabetes presents with chest pain and elevated troponin?",
        "expected_domains_any_of": ["cardiology", "endocrinology", "internal medicine", "emergency", "diagnosis", "medication", "treatment"],
        "should_conflict": True,
    },
    {
        "id": "pharmacy-interaction",
        "domain": "pharmacy",
        "question": "What drug interactions and dose adjustments should be considered for a patient on warfarin who requires a new SSRI prescription?",
        "expected_domains_any_of": ["pharmacology", "drug interactions", "psychiatry", "dosage", "adverse effects"],
        "should_conflict": True,
    },
    {
        "id": "finance-acquisition",
        "domain": "finance",
        "question": "What are the valuation, risk, and regulatory considerations for acquiring a fintech startup with high growth but negative cash flow?",
        "expected_domains_any_of": ["finance", "valuation", "risk", "regulatory", "market", "legal", "liquidity"],
        "should_conflict": True,
    },
    {
        "id": "cross-domain-simple",
        "domain": None,
        "question": "What are the key risks in launching a new pharmaceutical product in an emerging market?",
        "expected_domains_any_of": ["regulatory", "market", "risk", "finance", "supply chain"],
        "should_conflict": False,
    },
]


class TestDeliberationCreate:

    def test_health(self, authed_api):
        r = authed_api.get(authed_api.url("/api/deliberation/health"))
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "pipeline" in data

    def test_question_too_short(self, authed_api):
        r = authed_api.post(authed_api.url("/api/deliberation/sessions"), json={
            "question": "hi",
        })
        assert r.status_code == 422

    def test_domain_count_out_of_range(self, authed_api):
        for bad in [0, 1, 2, 11, 20]:
            r = authed_api.post(authed_api.url("/api/deliberation/sessions"), json={
                "question":     "What are the key financial risks in a cross-border acquisition?",
                "domain_count": bad,
            })
            assert r.status_code == 422, f"domain_count={bad} should be rejected"

    @pytest.mark.parametrize("tc", DELIBERATION_QUESTIONS, ids=[t["id"] for t in DELIBERATION_QUESTIONS])
    def test_sync_deliberation(self, tc, authed_api, healthcare_tenant, pharmacy_tenant, finance_tenant):
        tenant_id = None
        if tc["domain"] == "healthcare":
            tenant_id = healthcare_tenant
        elif tc["domain"] == "pharmacy":
            tenant_id = pharmacy_tenant
        elif tc["domain"] == "finance":
            tenant_id = finance_tenant

        payload = {
            "question":     tc["question"],
            "domain_count": 7,
            "async_mode":   False,
        }
        if tenant_id:
            payload["tenant_id"] = tenant_id

        start = time.time()
        r = authed_api.post(authed_api.url("/api/deliberation/sessions"), json=payload, timeout=120)
        elapsed = time.time() - start

        assert r.status_code in (200, 201, 202), f"Deliberation failed: {r.status_code} {r.text[:500]}"
        data = r.json()

        # Status must be done for sync mode
        assert data["status"] == "done", f"Expected done, got {data['status']}"

        # Domains
        assert "domains" in data and len(data["domains"]) >= 3, "Need at least 3 domains"
        domain_names_lower = " ".join(d["name"].lower() for d in data["domains"])
        expected_hit = any(exp.lower() in domain_names_lower for exp in tc["expected_domains_any_of"])
        assert expected_hit, (
            f"None of expected domains {tc['expected_domains_any_of']} found in: "
            + [d["name"] for d in data["domains"]].__repr__()
        )

        # Verticals
        assert "verticals" in data and len(data["verticals"]) >= 3
        for v in data["verticals"]:
            assert v.get("findings"), f"Empty findings for domain {v.get('domain')}"
            assert 0.0 <= v.get("confidence", 0.0) <= 1.0

        # Synthesis
        synth = data.get("synthesis")
        assert synth is not None
        assert synth.get("final_answer"), "Empty final_answer in synthesis"
        assert synth.get("agreements"), "Empty agreements in synthesis"

        if tc["should_conflict"]:
            # Conflict field should be present and non-trivial
            conflicts = synth.get("conflicts", "")
            assert conflicts and len(conflicts) > 20, \
                f"Expected conflicts for complex question, got: '{conflicts}'"

        # Unique insights
        assert synth.get("unique_insights"), "Empty unique_insights"

        # Latency — sync deliberation under 90s
        assert elapsed < 90, f"Deliberation took {elapsed:.1f}s — exceeds 90s threshold"

        print(f"\n[{tc['id']}] {elapsed:.1f}s | confidence={synth.get('confidence'):.2f} "
              f"| domains={[d['name'] for d in data['domains']]}")


class TestDeliberationAsync:

    def test_async_mode_returns_immediately(self, authed_api):
        start = time.time()
        r = authed_api.post(authed_api.url("/api/deliberation/sessions"), json={
            "question":   "What are the regulatory risks of launching an AI-powered medical device in the EU?",
            "async_mode": True,
        }, timeout=10)
        elapsed = time.time() - start
        assert r.status_code in (200, 201, 202)
        data = r.json()
        assert "session_id" in data
        assert data.get("async") is True
        assert data.get("status") in ("discovering", "created", "querying")
        assert elapsed < 5.0, f"Async call took {elapsed:.1f}s — should return in <5s"
        return data["session_id"]

    def test_poll_to_completion(self, authed_api):
        r = authed_api.post(authed_api.url("/api/deliberation/sessions"), json={
            "question":   "What is the impact of rising interest rates on fintech lending business models?",
            "async_mode": True,
        })
        session_id = r.json()["session_id"]
        poll_url = authed_api.url(f"/api/deliberation/sessions/{session_id}")

        for attempt in range(30):
            pr = authed_api.get(poll_url)
            status = pr.json()["status"]
            if status == "done":
                data = pr.json()
                assert data["synthesis"] is not None
                return
            if status == "failed":
                pytest.fail(f"Session {session_id} failed")
            time.sleep(5)
        pytest.fail(f"Session {session_id} never reached 'done' after 150s")


class TestDeliberationSession:

    @pytest.fixture(scope="class")
    def completed_session(self, authed_api, finance_tenant):
        r = authed_api.post(authed_api.url("/api/deliberation/sessions"), json={
            "question":   "What should we consider before a cross-border M&A acquisition in Southeast Asia?",
            "tenant_id":  finance_tenant,
            "async_mode": False,
        }, timeout=120)
        assert r.status_code in (200, 201, 202)
        return r.json()

    def test_get_session_by_id(self, authed_api, completed_session):
        sid = completed_session["session_id"]
        r = authed_api.get(authed_api.url(f"/api/deliberation/sessions/{sid}"))
        assert r.status_code == 200
        assert r.json()["session_id"] == sid

    def test_get_domains_endpoint(self, authed_api, completed_session):
        sid = completed_session["session_id"]
        r = authed_api.get(authed_api.url(f"/api/deliberation/sessions/{sid}/domains"))
        assert r.status_code == 200
        data = r.json()
        assert "domains" in data
        assert len(data["domains"]) >= 3

    def test_followup_question(self, authed_api, completed_session):
        sid = completed_session["session_id"]
        r = authed_api.post(authed_api.url(f"/api/deliberation/sessions/{sid}/followup"), json={
            "question": "Which of the identified risks should we address first?",
        })
        assert r.status_code == 200
        data = r.json()
        assert "answer" in data
        assert len(data["answer"]) > 50, "Follow-up answer is too short"

    def test_followup_does_not_consume_quota(self, authed_api, completed_session):
        """Follow-up on an existing session is free."""
        sid = completed_session["session_id"]
        for _ in range(3):
            r = authed_api.post(authed_api.url(f"/api/deliberation/sessions/{sid}/followup"), json={
                "question": "Can you elaborate on the regulatory risks?",
            })
            assert r.status_code == 200

    def test_list_sessions(self, authed_api, completed_session):
        r = authed_api.get(authed_api.url("/api/deliberation/sessions"))
        assert r.status_code == 200
        sessions = r.json()
        assert isinstance(sessions, list)
        sids = [s["session_id"] for s in sessions]
        assert completed_session["session_id"] in sids

    def test_session_not_found(self, authed_api):
        r = authed_api.get(authed_api.url("/api/deliberation/sessions/00000000-0000-0000-0000-000000000000"))
        assert r.status_code == 404
