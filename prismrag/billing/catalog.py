"""PrismRAG — single source of truth for sellable plans + Stripe price IDs.

Prices mirror web/index.html#pricing (PrismRAG Knowledge Graph column).
All paid plans are monthly subscriptions in Stripe (recurring interval=month).
Deliberation limits are bundled per tier — not separate Stripe line items.
"""
from __future__ import annotations

import os
from typing import Any

# Legacy live price IDs (superseded products — keep for webhook mapping on old subs)
_LEGACY_PRICE_TO_PLAN: dict[str, str] = {
    "price_1TjT2B2LIcUqGpPtn5Yc6qBL": "starter",
    "price_1TjT2F2LIcUqGpPtjsqOzXOD": "professional",
    "price_1TjT2G2LIcUqGpPtil4pNZJ3": "enterprise",
    "price_1TjTqb2LIcUqGpPtS5y5OG0T": "starter",
    "price_1TjTqc2LIcUqGpPt9qLHEadw": "professional",
    "price_1TjTqd2LIcUqGpPtTGuj7wij": "enterprise",
}

# Homepage: web/index.html#pricing — PrismRAG monthly subscription amounts (USD cents)
PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_cents": 0,
        "billing_interval": "month",
        "billing_type": "subscription",
        "description": "Try PrismRAG with no commitment",
        "cta": "Start Free",
        "popular": False,
        "sellable": False,
        "stripe_checkout": False,
        "monthly_chunks": 5_000,
        "monthly_deliberations": 5,
    },
    "starter": {
        "name": "Starter",
        "price_cents": 4_900,
        "billing_interval": "month",
        "billing_type": "subscription",
        "description": "For teams building their first pipeline",
        "cta": "Get started",
        "popular": False,
        "sellable": True,
        "stripe_checkout": True,
        "monthly_chunks": 50_000,
        "monthly_deliberations": 50,
        "stripe_product_name": "Insight PrismRAG · Starter",
        "stripe_lookup_key": "insight_prismrag_starter_monthly",
        "stripe_statement_descriptor": "PRISMRAG STARTER",
    },
    "professional": {
        "name": "Professional",
        "price_cents": 19_900,
        "billing_interval": "month",
        "billing_type": "subscription",
        "description": "Full ML stack for production deployments",
        "cta": "Start Professional",
        "popular": True,
        "sellable": True,
        "stripe_checkout": True,
        "monthly_chunks": 500_000,
        "monthly_deliberations": 500,
        "stripe_product_name": "Insight PrismRAG · Professional",
        "stripe_lookup_key": "insight_prismrag_professional_monthly",
        "stripe_statement_descriptor": "PRISMRAG PRO",
    },
    "enterprise": {
        "name": "Enterprise",
        "price_cents": 49_900,
        "billing_interval": "month",
        "billing_type": "subscription",
        "description": "Unlimited scale, SCIM SSO, CMEK, and dedicated support",
        "cta": "Start Enterprise",
        "popular": False,
        "sellable": True,
        "stripe_checkout": True,
        "monthly_chunks": 0,
        "monthly_deliberations": 0,
        "stripe_product_name": "Insight PrismRAG · Enterprise",
        "stripe_lookup_key": "insight_prismrag_enterprise_monthly",
        "stripe_statement_descriptor": "PRISMRAG ENT",
    },
}

PAID_PLANS = ("starter", "professional", "enterprise")

# Informational breakdown shown on homepage (Deliberation column) — included in plan, not billed separately
DELIBERATION_REFERENCE_MONTHLY_CENTS: dict[str, int] = {
    "free": 0,
    "starter": 2_900,
    "professional": 9_900,
    "enterprise": 0,
}


def price_env_key(plan: str) -> str:
    if plan == "professional":
        return "STRIPE_PRICE_PROFESSIONAL"
    return f"STRIPE_PRICE_{plan.upper()}"


def get_price_ids() -> dict[str, str]:
    """Current Stripe Price IDs from environment."""
    return {
        plan: os.getenv(price_env_key(plan), "").strip()
        for plan in PAID_PLANS
    }


def get_plan_from_price_id(price_id: str) -> str | None:
    """Map a Stripe price ID to an internal plan name."""
    for plan, pid in get_price_ids().items():
        if pid and pid == price_id:
            return plan
    return _LEGACY_PRICE_TO_PLAN.get(price_id)


def format_price_display(plan_id: str) -> str:
    meta = PLAN_CATALOG.get(plan_id, {})
    cents = meta.get("price_cents")
    if cents is None:
        return "Custom"
    if cents == 0:
        return "$0"
    return f"${cents // 100:,}"


def format_price_period(plan_id: str) -> str:
    interval = PLAN_CATALOG.get(plan_id, {}).get("billing_interval", "month")
    return f"/{interval}"


def stripe_plan_specs() -> list[dict[str, Any]]:
    """Specs for scripts/setup_stripe_products.py — monthly recurring only."""
    specs = []
    for plan in PAID_PLANS:
        meta = PLAN_CATALOG[plan]
        chunks = meta["monthly_chunks"]
        delibs = meta["monthly_deliberations"]
        chunk_txt = "unlimited chunks" if chunks <= 0 else f"{chunks:,} chunks/month"
        delib_txt = "unlimited deliberations" if delibs <= 0 else f"{delibs} deliberations/month"
        specs.append({
            "plan": plan,
            "name": meta["stripe_product_name"],
            "description": (
                f"Monthly subscription — PrismRAG Knowledge Graph + Deliberation. "
                f"{chunk_txt}, {delib_txt}."
            ),
            "amount_cents": meta["price_cents"],
            "lookup_key": meta["stripe_lookup_key"],
            "statement_descriptor": meta["stripe_statement_descriptor"],
            "nickname": f"{meta['stripe_product_name']} — Monthly",
        })
    return specs


def is_stripe_configured() -> bool:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key or key.startswith("PASTE_") or key == "not-configured":
        return False
    prices = get_price_ids()
    return all(prices.get(p) and not prices[p].startswith("not-configured") for p in PAID_PLANS)


def stripe_status() -> dict[str, Any]:
    """Health snapshot for /status and ops."""
    prices = get_price_ids()
    missing = [p for p in PAID_PLANS if not prices.get(p) or prices[p].startswith("not-configured")]
    pk = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    wh = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return {
        "configured": is_stripe_configured(),
        "billing_type": "subscription",
        "billing_interval": "month",
        "secret_key_set": bool(os.getenv("STRIPE_SECRET_KEY", "").startswith("sk_")),
        "publishable_key_set": bool(pk and pk.startswith("pk_")),
        "webhook_secret_set": bool(wh and wh.startswith("whsec_")),
        "price_ids": prices,
        "homepage_prices_usd": {
            p: PLAN_CATALOG[p]["price_cents"] // 100 for p in (*PAID_PLANS, "free")
        },
        "missing_price_plans": missing,
        "billing_group": "prismrag_saas",
    }
