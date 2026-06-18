"""Unit tests for billing catalog (homepage price alignment)."""
from prismrag.billing.catalog import (
    PLAN_CATALOG,
    format_price_display,
    stripe_plan_specs,
)


def test_homepage_monthly_prices():
    assert PLAN_CATALOG["free"]["price_cents"] == 0
    assert PLAN_CATALOG["starter"]["price_cents"] == 4_900
    assert PLAN_CATALOG["professional"]["price_cents"] == 19_900
    assert PLAN_CATALOG["enterprise"]["price_cents"] == 49_900


def test_all_paid_plans_are_monthly_subscriptions():
    for plan in ("starter", "professional", "enterprise"):
        meta = PLAN_CATALOG[plan]
        assert meta["billing_type"] == "subscription"
        assert meta["billing_interval"] == "month"
        assert meta["stripe_checkout"] is True


def test_stripe_specs_recurring_monthly():
    specs = stripe_plan_specs()
    assert len(specs) == 3
    assert specs[0]["amount_cents"] == 4_900
    assert "month" in specs[0]["lookup_key"]


def test_price_display():
    assert format_price_display("starter") == "$49"
    assert format_price_display("professional") == "$199"
    assert format_price_display("enterprise") == "$499"
