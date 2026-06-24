"""Step 6 — evaluation harness: aggregate parity metrics across domains."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from tests.conftest import DOMAIN_CONFIGS
from tests.fixtures.lib_conftest import inline_records_from_mapping


@dataclass
class EvalResult:
    domain: str
    ingest_ok: bool = False
    community_count: int = 0
    edge_count: int = 0
    search_hits: int = 0
    category_accuracy: float = 0.0
    avg_quality: float | None = None
    errors: list[str] = field(default_factory=list)


def _evaluate_domain(domain: str, mapping: dict, queries: list[tuple[str, str]]) -> EvalResult:
    from prismrag_patch import PrismRAG

    result = EvalResult(domain=domain)
    rag = PrismRAG(mapping=mapping, tenant_id=f"eval-{domain}")
    try:
        job = rag.ingest(records=inline_records_from_mapping(mapping))
        result.ingest_ok = job["status"] == "completed"
        result.community_count = job.get("community_count", 0)
        result.edge_count = job.get("edge_count", 0)

        hits_total = 0
        correct = 0
        for query, expected_cat in queries:
            data = rag.search(query, top_k=5)
            results = data.get("results", [])
            hits_total += len(results)
            if results and results[0].get("category_slug") == expected_cat:
                correct += 1
        result.search_hits = hits_total
        result.category_accuracy = correct / max(len(queries), 1)

        quality = rag.chunk_quality()
        result.avg_quality = quality["summary"].get("avg_quality")
    except Exception as exc:
        result.errors.append(str(exc))
    return result


class TestStep06Evaluation:
    @pytest.mark.parametrize("domain", ["healthcare", "pharmacy", "finance"])
    def test_domain_evaluation_report(self, domain):
        cfg = DOMAIN_CONFIGS[domain]
        ev = _evaluate_domain(domain, cfg["mapping"], cfg["search_queries"])
        assert ev.ingest_ok, ev.errors
        assert ev.community_count >= 1
        assert ev.edge_count >= 1
        assert ev.search_hits > 0
        assert ev.avg_quality is not None
        print(json.dumps(ev.__dict__, indent=2))

    def test_full_evaluation_summary(self):
        summary = []
        for domain, cfg in DOMAIN_CONFIGS.items():
            ev = _evaluate_domain(domain, cfg["mapping"], cfg["search_queries"])
            summary.append(ev.__dict__)
        report = {
            "domains": len(summary),
            "ingest_pass": sum(1 for s in summary if s["ingest_ok"]),
            "avg_category_accuracy": sum(s["category_accuracy"] for s in summary) / len(summary),
            "details": summary,
        }
        print(json.dumps(report, indent=2))
        assert report["ingest_pass"] == report["domains"]
