"""Tests — Stripe billing (requires STRIPE_SECRET_KEY + price IDs in .env)."""
import os
import pytest
from tests.conftest import BILLING_API, AUTH_API


@pytest.mark.stripe
class TestBilling:
    def test_list_plans(self, api):
        r = api.get(api.url(f"{BILLING_API}/plans"))
        assert r.status_code == 200
        data = r.json()
        assert "plans" in data
        assert len(data["plans"]) >= 4
        ids = {p["id"] for p in data["plans"]}
        assert "free" in ids and "starter" in ids

    def test_checkout_starter_session(self, authed_api, stripe_configured):
        starter_price = os.getenv("STRIPE_PRICE_STARTER", "")
        if starter_price.startswith("PASTE_"):
            pytest.skip("STRIPE_PRICE_STARTER not set")
        r = authed_api.post(authed_api.url(f"{BILLING_API}/checkout"), json={"plan": "starter"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "redirect" in data
        assert "checkout.stripe.com" in data["redirect"] or data["redirect"].startswith("https://")

    def test_checkout_enterprise_subscription(self, authed_api, stripe_configured):
        r = authed_api.post(authed_api.url(f"{BILLING_API}/checkout"), json={"plan": "enterprise"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "redirect" in data
        assert "checkout.stripe.com" in data["redirect"] or data["redirect"].startswith("https://")

    def test_plans_monthly_subscription(self, api):
        r = api.get(api.url(f"{BILLING_API}/plans"))
        data = r.json()
        assert data.get("billing_type") == "subscription"
        assert data.get("billing_interval") == "month"
        starter = next(p for p in data["plans"] if p["id"] == "starter")
        assert starter["price_cents"] == 4900
        assert starter["interval"] == "month"
        enterprise = next(p for p in data["plans"] if p["id"] == "enterprise")
        assert enterprise["price_cents"] == 49900

    def test_portal_without_customer(self, authed_api):
        r = authed_api.post(authed_api.url(f"{BILLING_API}/portal"), json={})
        assert r.status_code == 400

    def test_stripe_customer_created_on_checkout(self, authed_api, stripe_configured):
        r = authed_api.post(authed_api.url(f"{BILLING_API}/checkout"), json={"plan": "starter"})
        assert r.status_code == 200
        me = authed_api.get(authed_api.url(f"{AUTH_API}/me")).json()
        assert me.get("stripeCustomerId"), "Expected stripe_customer_id after checkout session create"
