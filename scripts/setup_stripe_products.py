#!/usr/bin/env python3
"""
Create Insight PrismRAG monthly subscription products & prices in Stripe.

Prices are read from prismrag.billing.catalog (same as web/index.html#pricing).
Every price is recurring interval=month — never one-time.

Usage:
  python scripts/setup_stripe_products.py
  python scripts/setup_stripe_products.py --write-env
  python scripts/setup_stripe_products.py --force-new

Requires STRIPE_SECRET_KEY in environment or .env (via dotenv).
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from prismrag.billing.catalog import PAID_PLANS, stripe_plan_specs

_BILLING_GROUP = "prismrag_saas"
_APP = "insight_prismrag"

ENV_KEYS = {
    "starter": "STRIPE_PRICE_STARTER",
    "professional": "STRIPE_PRICE_PROFESSIONAL",
    "enterprise": "STRIPE_PRICE_ENTERPRISE",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Insight PrismRAG monthly Stripe subscriptions")
    parser.add_argument("--write-env", action="store_true", help="Update .env with price IDs")
    parser.add_argument("--force-new", action="store_true", help="Create new product+price (skip lookup_key reuse)")
    args = parser.parse_args()

    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key or key.startswith("PASTE_"):
        print("ERROR: Set STRIPE_SECRET_KEY in .env (sk_test_... or sk_live_...)", file=sys.stderr)
        return 1

    import stripe

    stripe.api_key = key
    mode = "test" if key.startswith("sk_test_") else "live"
    print(f"Stripe mode: {mode}")
    print("Billing: monthly subscriptions only (recurring interval=month)\n")

    price_ids: dict[str, str] = {}

    for spec in stripe_plan_specs():
        if not args.force_new:
            existing = stripe.Price.list(lookup_keys=[spec["lookup_key"]], limit=1)
            if existing.data:
                price = existing.data[0]
                _assert_monthly_recurring(price, spec["plan"])
                print(f"  {spec['plan']}: exists {price.id} (${spec['amount_cents'] // 100}/mo)")
                price_ids[spec["plan"]] = price.id
                continue

        product = stripe.Product.create(
            name=spec["name"],
            description=spec["description"],
            statement_descriptor=spec["statement_descriptor"],
            type="service",
            metadata={
                "app": _APP,
                "billing_group": _BILLING_GROUP,
                "product_line": "prismrag",
                "prismrag_plan": spec["plan"],
                "billing_type": "subscription",
            },
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=spec["amount_cents"],
            currency="usd",
            recurring={"interval": "month", "interval_count": 1},
            lookup_key=spec["lookup_key"],
            nickname=spec["nickname"],
            transfer_lookup_key=True,
            metadata={
                "app": _APP,
                "billing_group": _BILLING_GROUP,
                "prismrag_plan": spec["plan"],
                "billing_interval": "month",
            },
        )
        print(f"  {spec['plan']}: created {price.id} (${spec['amount_cents'] // 100}/mo subscription)")
        price_ids[spec["plan"]] = price.id

    print("\nAdd to .env / GitHub secrets:")
    for plan, env_key in ENV_KEYS.items():
        print(f"{env_key}={price_ids[plan]}")

    if args.write_env:
        _patch_env(price_ids)
        print("\nUpdated .env with price IDs.")

    return 0


def _assert_monthly_recurring(price: object, plan: str) -> None:
    recurring = getattr(price, "recurring", None) or (price.get("recurring") if isinstance(price, dict) else None)
    if not recurring:
        raise SystemExit(f"ERROR: Stripe price for {plan} is not recurring — expected monthly subscription")
    interval = getattr(recurring, "interval", None) or recurring.get("interval")
    if interval != "month":
        raise SystemExit(f"ERROR: Stripe price for {plan} has interval={interval!r} — expected 'month'")


def _patch_env(price_ids: dict[str, str]) -> None:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    lines: list[str] = []
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = f.read().splitlines()

    updates = {ENV_KEYS[k]: v for k, v in price_ids.items()}
    seen = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")
    with open(env_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    sys.exit(main())
