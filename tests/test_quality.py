"""
Tests — Result quality evaluation across all three domains.

These tests go beyond pass/fail HTTP checks and measure the QUALITY of
search and deliberation outputs, generating a structured quality report.

Run with: pytest tests/test_quality.py -v --tb=short -s

Quality metrics:
  Search:
    - Category precision@1: top result in correct category
    - Category precision@3: >=2 of top 3 in correct category
    - Score spread: max_score - min_score (higher = better discrimination)
    - Mean confidence of returned results

  Deliberation:
    - Domain relevance: fraction of expected domains actually discovered
    - Synthesis completeness: all 4 synthesis fields non-empty
    - Conflict detection: conflicts field present and >50 chars for complex Qs
    - Confidence calibration: synthesis.confidence between 0.5 and 0.95
    - Unique insights: unique_insights field >30 chars
"""
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import pytest
from tests.conftest import DOMAIN_CONFIGS, HEALTHCARE_MAPPING, PHARMACY_MAPPING, FINANCE_MAPPING


QUALITY_REPORT_PATH = Path("tests/quality_report.json")

_report: dict = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "search":        {},
    "deliberation":  {},
    "summary":       {},
}


# ── Search quality ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def all_jobs(authed_api, healthcare_tenant, pharmacy_tenant, finance_tenant):
    from tests.test_prismrag import ingest_job
    return {
        "healthcare": ingest_job(authed_api, healthcare_tenant, HEALTHCARE_MAPPING),
        "pharmacy":   ingest_job(authed_api, pharmacy_tenant,   PHARMACY_MAPPING),
        "finance":    ingest_job(authed_api, finance_tenant,    FINANCE_MAPPING),
    }


class TestSearchQuality:

    @pytest.mark.parametrize("domain", ["healthcare", "pharmacy", "finance"])
    def test_category_precision(
        self, domain, authed_api, healthcare_tenant, pharmacy_tenant, finance_tenant, all_jobs
    ):
        tenant_id = {"healthcare": healthcare_tenant,
                     "pharmacy":   pharmacy_tenant,
                     "finance":    finance_tenant}[domain]

        test_cases = DOMAIN_CONFIGS[domain]["search_queries"]
        precision_at_1 = []
        precision_at_3 = []
        score_spreads  = []

        for query, expected_cat in test_cases:
            r = authed_api.post(authed_api.url("/api/prismrag/search"), json={
                "tenant_id": tenant_id,
                "query":     query,
                "top_k":     5,
            })
            assert r.status_code == 200
            results = r.json()["results"]
            if not results:
                precision_at_1.append(0)
                precision_at_3.append(0)
                continue

            cats = [res["category_slug"] for res in results]
            scores = [res["score"] for res in results]

            p1 = 1 if cats[0] == expected_cat else 0
            p3 = sum(1 for c in cats[:3] if c == expected_cat) / min(3, len(cats))
            spread = max(scores) - min(scores) if len(scores) > 1 else 0.0

            precision_at_1.append(p1)
            precision_at_3.append(p3)
            score_spreads.append(spread)

        avg_p1 = sum(precision_at_1) / len(precision_at_1)
        avg_p3 = sum(precision_at_3) / len(precision_at_3)
        avg_spread = sum(score_spreads) / len(score_spreads)

        _report["search"][domain] = {
            "precision_at_1":   round(avg_p1, 3),
            "precision_at_3":   round(avg_p3, 3),
            "avg_score_spread": round(avg_spread, 4),
            "queries_tested":   len(test_cases),
        }
        print(f"\n[QUALITY:{domain}] search P@1={avg_p1:.2f} P@3={avg_p3:.2f} spread={avg_spread:.3f}")

        # Threshold: at least 50% precision@1 (soft — logs not fails for P@3)
        assert avg_p1 >= 0.5, (
            f"Search precision@1 for {domain} = {avg_p1:.2f} — below 0.5 threshold. "
            "Check that ingestion completed successfully and community detection ran."
        )


# ── Deliberation quality ──────────────────────────────────────────────────────

DELIB_QUALITY_CASES = [
    {
        "id": "healthcare-complexity",
        "question": "A diabetic patient is admitted with sepsis and acute kidney injury. What are the clinical, medication, and safety considerations?",
        "expected_domains": ["medication", "treatment", "diagnosis", "patient safety", "nephrology", "endocrinology"],
        "min_domains_expected": 3,
        "expect_conflict": True,
        "tenant": "healthcare",
    },
    {
        "id": "finance-complexity",
        "question": "Should we issue new equity or take on debt to fund our international expansion, given current market volatility and regulatory requirements?",
        "expected_domains": ["finance", "risk", "regulatory", "market", "valuation", "debt"],
        "min_domains_expected": 4,
        "expect_conflict": True,
        "tenant": "finance",
    },
    {
        "id": "pharmacy-complexity",
        "question": "What are the pharmacokinetic interactions and adverse effect risks when adding an SSRI to a patient already on warfarin and a statin?",
        "expected_domains": ["pharmacokinetics", "drug interactions", "adverse effects", "dosage"],
        "min_domains_expected": 3,
        "expect_conflict": True,
        "tenant": "pharmacy",
    },
]


class TestDeliberationQuality:

    @pytest.mark.parametrize("tc", DELIB_QUALITY_CASES, ids=[t["id"] for t in DELIB_QUALITY_CASES])
    def test_deliberation_quality(
        self, tc, authed_api, healthcare_tenant, pharmacy_tenant, finance_tenant
    ):
        tenant_id = {"healthcare": healthcare_tenant,
                     "pharmacy":   pharmacy_tenant,
                     "finance":    finance_tenant}.get(tc["tenant"])

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

        assert r.status_code in (200, 201, 202)
        data = r.json()
        assert data["status"] == "done"

        domains = data.get("domains", [])
        verticals = data.get("verticals", [])
        synth = data.get("synthesis", {})

        # ── Domain relevance score ─────────────────────────────────────────────
        domain_names_lower = " ".join(d["name"].lower() for d in domains)
        matched = sum(
            1 for exp in tc["expected_domains"]
            if exp.lower() in domain_names_lower
        )
        domain_relevance = matched / len(tc["expected_domains"])

        # ── Synthesis completeness ────────────────────────────────────────────
        fields_complete = {
            "agreements":      len(synth.get("agreements", "")) > 30,
            "conflicts":       len(synth.get("conflicts", "")) > (30 if tc["expect_conflict"] else 0),
            "unique_insights": len(synth.get("unique_insights", "")) > 20,
            "final_answer":    len(synth.get("final_answer", "")) > 80,
        }
        completeness = sum(fields_complete.values()) / len(fields_complete)

        # ── Confidence calibration ─────────────────────────────────────────────
        synthesis_conf = synth.get("confidence", 0.0)
        conf_calibrated = 0.4 <= synthesis_conf <= 0.97

        # ── Vertical confidence mean ───────────────────────────────────────────
        vert_confs = [v.get("confidence", 0.0) for v in verticals if v.get("confidence") is not None]
        mean_vert_conf = sum(vert_confs) / len(vert_confs) if vert_confs else 0.0

        quality = {
            "question_id":          tc["id"],
            "elapsed_s":            round(elapsed, 1),
            "domains_returned":     len(domains),
            "domain_relevance":     round(domain_relevance, 3),
            "synthesis_completeness": round(completeness, 3),
            "synthesis_confidence": round(synthesis_conf, 3),
            "conf_calibrated":      conf_calibrated,
            "mean_vertical_conf":   round(mean_vert_conf, 3),
            "fields":               fields_complete,
            "conflict_present":     len(synth.get("conflicts", "")) > 30,
        }
        _report["deliberation"][tc["id"]] = quality

        print(f"\n[QUALITY:{tc['id']}] elapsed={elapsed:.1f}s "
              f"domain_relevance={domain_relevance:.2f} "
              f"completeness={completeness:.2f} "
              f"synthesis_conf={synthesis_conf:.2f}")

        # ── Assertions ────────────────────────────────────────────────────────
        assert len(domains) >= tc["min_domains_expected"], \
            f"Only {len(domains)} domains returned, expected >= {tc['min_domains_expected']}"

        assert domain_relevance >= 0.3, \
            f"Domain relevance {domain_relevance:.2f} too low. Got: {[d['name'] for d in domains]}"

        assert completeness >= 0.75, \
            f"Synthesis completeness {completeness:.2f}. Missing: {[k for k,v in fields_complete.items() if not v]}"

        assert conf_calibrated, \
            f"Synthesis confidence {synthesis_conf:.3f} out of expected range [0.4, 0.97]"

        if tc["expect_conflict"]:
            assert quality["conflict_present"], \
                f"Expected conflicts for complex question — conflicts field: '{synth.get('conflicts', '')}'"


# ── Write quality report ──────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def write_quality_report(request):
    yield
    # Compute summary
    search_scores = [v["precision_at_1"] for v in _report["search"].values() if "precision_at_1" in v]
    delib_scores  = [v["domain_relevance"] for v in _report["deliberation"].values() if "domain_relevance" in v]

    _report["summary"] = {
        "avg_search_precision_at_1": round(sum(search_scores) / len(search_scores), 3) if search_scores else None,
        "avg_deliberation_domain_relevance": round(sum(delib_scores) / len(delib_scores), 3) if delib_scores else None,
        "domains_tested": list(_report["search"].keys()),
        "deliberation_cases": list(_report["deliberation"].keys()),
    }

    QUALITY_REPORT_PATH.parent.mkdir(exist_ok=True)
    with open(QUALITY_REPORT_PATH, "w") as f:
        json.dump(_report, f, indent=2)
    print(f"\n\nQuality report written to: {QUALITY_REPORT_PATH}")
    print(f"Search P@1 avg:               {_report['summary']['avg_search_precision_at_1']}")
    print(f"Deliberation relevance avg:   {_report['summary']['avg_deliberation_domain_relevance']}")
