"""PrismRAG — Stripe billing integration."""
from __future__ import annotations

import os

import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET  = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Stripe Price IDs — create these once in your Stripe dashboard
# or via the Stripe API and set the env vars.
PRICE_IDS: dict[str, str] = {
    "starter":      os.getenv("STRIPE_PRICE_STARTER",      "price_starter_monthly"),
    "professional": os.getenv("STRIPE_PRICE_PROFESSIONAL", "price_professional_monthly"),
    "enterprise":   os.getenv("STRIPE_PRICE_ENTERPRISE",   "price_enterprise_monthly"),
}

PLAN_FROM_PRICE: dict[str, str] = {v: k for k, v in PRICE_IDS.items()}


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
        metadata={"prismrag_user_id": user_id},
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
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Unknown plan: {plan}")

    customer_id = get_or_create_customer(user_id, email, name)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        subscription_data={
            "metadata": {"prismrag_user_id": user_id, "plan": plan}
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
    """
    Verify + parse a Stripe webhook event.
    Returns the event dict or raises on invalid signature.
    """
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
    from prismrag.db import get_conn, release_conn
    from datetime import datetime, timezone

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


def process_webhook_event(event: dict) -> str:
    """Handle the relevant Stripe events. Returns a status string."""
    etype = event["type"]
    obj   = event["data"]["object"]

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        price_id = obj["items"]["data"][0]["price"]["id"]
        plan     = PLAN_FROM_PRICE.get(price_id, "starter")
        _update_subscription_in_db(
            stripe_customer_id=obj["customer"],
            plan=plan,
            status=obj["status"],
            subscription_id=obj["id"],
            period_end=obj.get("current_period_end"),
        )
        return f"subscription {obj['status']}"

    if etype == "customer.subscription.deleted":
        _update_subscription_in_db(
            stripe_customer_id=obj["customer"],
            plan="free",
            status="canceled",
            subscription_id=obj["id"],
            period_end=None,
        )
        return "subscription canceled → downgraded to free"

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
