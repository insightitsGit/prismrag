"""Tests — Status page and SLA API."""
from tests.conftest import STATUS_API


class TestStatus:
    def test_public_status(self, api):
        r = api.get(api.url(f"{STATUS_API}"))
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ("operational", "degraded", "major_outage")
        assert "components" in data
        assert "database" in data["components"]

    def test_sla_metrics(self, api):
        r = api.get(api.url(f"{STATUS_API}/sla"))
        assert r.status_code == 200
        data = r.json()
        assert data.get("uptime_target_pct") == 99.9
        assert "contact" in data
