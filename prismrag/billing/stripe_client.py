"""PrismRAG — Stripe billing integration."""
from __future__ import annotations

import os

import stripe

from prismrag.billing.catalog import (
    PAID_PLANS,
    get_plan_from_price_id,
    get_price_ids,
    is_stripe_configured,
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

PRICE_IDS: dict[str, str] = get_price_ids()


def _refresh_price_ids() -> None:
    """Reload price IDs from env (tests may patch os.environ)."""
    global PRICE_IDS
    PRICE_IDS = get_price_ids()


def get_or_create_customer(user_id: str, email: str, name: str) -> str:
    """Return Stripe customer ID, creating one if needed."""
    from prismrag.db import get_conn, release_conn

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT stripe_customer_id FROM prismrag.user_account WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    finally:
        release_conn(conn)

    customer = stripe.Customer.create(
        email=email,
        name=name,
        metadata={
            "prismrag_user_id": user_id,
            "app": "insight_prismrag",
            "billing_group": "prismrag_saas",
        },
    )
    cid = customer["id"]

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prismrag.user_account SET stripe_customer_id = %s WHERE id = %s",
            (cid, user_id),
        )
        conn.commit()
    finally:
        release_conn(conn)

    return cid


def create_checkout_session(
    user_id: str,
    email: str,
    name: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session. Returns the session URL."""
    _refresh_price_ids()
    if not is_stripe_configured():
        raise RuntimeError("Stripe is not fully configured (secret key + price IDs required)")

    if plan not in PAID_PLANS:
        raise ValueError(f"Plan is not available for checkout: {plan}")

    price_id = PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"No Stripe price configured for plan: {plan}")

    customer_id = get_or_create_customer(user_id, email, name)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        subscription_data={
            "metadata": {
                "prismrag_user_id": user_id,
                "plan": plan,
                "billing_group": "prismrag_saas",
            }
        },
        metadata={
            "prismrag_user_id": user_id,
            "plan": plan,
            "billing_group": "prismrag_saas",
        },
        allow_promotion_codes=True,
    )
    return session["url"]


def create_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Billing Portal session for subscription management."""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session["url"]


def handle_webhook(payload: bytes, sig_header: str) -> dict | None:
    """Verify + parse a Stripe webhook event."""
    if not STRIPE_WEBHOOK_SECRET or STRIPE_WEBHOOK_SECRET.startswith("PASTE_"):
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as exc:
        raise ValueError(f"Invalid Stripe signature: {exc}") from exc

    return event


def _update_subscription_in_db(
    stripe_customer_id: str,
    plan: str,
    status: str,
    subscription_id: str,
    period_end: int | None,
) -> None:
    from datetime import datetime, timezone

    from prismrag.db import get_conn, release_conn

    period_end_dt = (
        datetime.fromtimestamp(period_end, tz=timezone.utc) if period_end else None
    )

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE prismrag.user_account
            SET plan                    = %s,
                subscription_status     = %s,
                stripe_subscription_id  = %s,
                subscription_period_end = %s,
                updated_at              = now()
            WHERE stripe_customer_id = %s
            """,
            (plan, status, subscription_id, period_end_dt, stripe_customer_id),
        )
        conn.commit()
    finally:
        release_conn(conn)


def _subscription_price_id(subscription_obj: dict) -> str | None:
    items = subscription_obj.get("items", {}).get("data", [])
    if not items:
        return None
    price = items[0].get("price") or {}
    return price.get("id")


def _apply_subscription_event(subscription_obj: dict) -> str:
    price_id = _subscription_price_id(subscription_obj)
    if not price_id:
        return "subscription event missing price"
    plan = get_plan_from_price_id(price_id)
    if not plan:
        return f"unknown price id: {price_id}"
    _update_subscription_in_db(
        stripe_customer_id=subscription_obj["customer"],
        plan=plan,
        status=subscription_obj["status"],
        subscription_id=subscription_obj["id"],
        period_end=subscription_obj.get("current_period_end"),
    )
    return f"subscription {subscription_obj['status']} → {plan}"


def process_webhook_event(event: dict) -> str:
    """Handle Stripe billing events. Returns a status string."""
    etype = event["type"]
    obj = event["data"]["object"]

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        return _apply_subscription_event(obj)

    if etype == "customer.subscription.deleted":
        _update_subscription_in_db(
            stripe_customer_id=obj["customer"],
            plan="free",
            status="canceled",
            subscription_id=obj["id"],
            period_end=None,
        )
        return "subscription canceled → downgraded to free"

    if etype == "checkout.session.completed":
        if obj.get("mode") != "subscription":
            return "checkout completed (non-subscription)"
        sub_id = obj.get("subscription")
        if not sub_id:
            return "checkout completed without subscription id"
        subscription = stripe.Subscription.retrieve(sub_id)
        return _apply_subscription_event(subscription)

    if etype == "invoice.payment_failed":
        from prismrag.db import get_conn, release_conn

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE prismrag.user_account SET subscription_status = 'past_due' "
                "WHERE stripe_customer_id = %s",
                (obj["customer"],),
            )
            conn.commit()
        finally:
            release_conn(conn)
        return "payment_failed → past_due"

    return f"ignored event: {etype}"
