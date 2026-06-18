"""PrismRAG — Billing API routes (Stripe)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from prismrag.auth.auth import get_current_user
from prismrag.billing.catalog import (
    PAID_PLANS,
    PLAN_CATALOG,
    format_price_display,
    format_price_period,
    is_stripe_configured,
    stripe_status,
)
from prismrag.billing.stripe_client import (
    create_checkout_session,
    create_portal_session,
    handle_webhook,
    process_webhook_event,
    STRIPE_PUBLISHABLE_KEY,
)

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])
billing_router = router

BASE_URL = os.getenv("PRISMRAG_BASE_URL", "http://localhost:8001").rstrip("/")
PRICING_URL = f"{BASE_URL}/index.html#pricing"


class CheckoutIn(BaseModel):
    plan: str


def _plan_payload(pid: str, limits: dict) -> dict:
    meta = PLAN_CATALOG.get(pid, {"name": pid.title(), "price_cents": 0, "description": ""})

    def _fmt_chunks(n: int) -> str:
        if n <= 0:
            return "Unlimited chunks"
        return f"{n:,} chunks / month"

    features = [_fmt_chunks(limits["monthly_chunks"])]
    mt = limits["max_tenants"]
    features.append("Unlimited workspaces" if mt < 0 else f"{mt} workspace(s)")
    if limits.get("graph_rag"):
        features.append("Graph RAG retrieval")
    if limits.get("tier2_mlp"):
        features.append("Tier-2 MLP training")
    if limits.get("bridge_vectors"):
        features.append("Bridge vectors")
    if pid == "enterprise":
        features.extend(["SCIM SSO", "CMEK", "99.9% SLA"])

    price_cents = meta.get("price_cents")
    interval = meta.get("billing_interval", "month")
    return {
        "id": pid,
        "name": meta["name"],
        "price": price_cents,
        "price_cents": price_cents,
        "price_display": format_price_display(pid),
        "price_period": format_price_period(pid),
        "description": meta.get("description", ""),
        "currency": "usd",
        "interval": interval,
        "billing_type": meta.get("billing_type", "subscription"),
        "monthly_deliberations": meta.get("monthly_deliberations"),
        "features": features,
        "cta": meta.get("cta", "Select"),
        "popular": meta.get("popular", False),
        "sellable": meta.get("sellable", False),
        "stripe_checkout": meta.get("stripe_checkout", False),
    }


@router.get("/config")
def billing_config():
    """Stripe wiring status (no secrets exposed)."""
    return stripe_status()


@router.get("/plans")
def list_plans():
    """Return sellable plans + Stripe publishable key for the dashboard."""
    from prismrag.plans import get_all_plans

    plans_db = get_all_plans()
    order = ("free", "starter", "professional", "enterprise")
    plans = [
        _plan_payload(pid, plans_db[pid])
        for pid in order
        if pid in plans_db
    ]
    pk = STRIPE_PUBLISHABLE_KEY if STRIPE_PUBLISHABLE_KEY.startswith("pk_") else ""
    return {
        "stripePublishableKey": pk,
        "publishable_key": pk,
        "stripe_configured": is_stripe_configured(),
        "billing_type": "subscription",
        "billing_interval": "month",
        "plans": plans,
    }


@router.post("/checkout")
def create_checkout(body: CheckoutIn, user: dict = Depends(get_current_user)):
    if body.plan == "free":
        return {"redirect": f"{BASE_URL}/dashboard.html"}

    if body.plan not in PAID_PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    if not is_stripe_configured():
        raise HTTPException(
            status_code=503,
            detail="Billing is not configured. Contact support.",
        )

    try:
        url = create_checkout_session(
            user_id=user["id"],
            email=user["email"],
            name=user.get("fullName") or user["email"],
            plan=body.plan,
            success_url=f"{BASE_URL}/dashboard.html?upgrade=success",
            cancel_url=PRICING_URL,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"redirect": url}


@router.post("/portal")
def billing_portal(user: dict = Depends(get_current_user)):
    if not is_stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured")

    cid = user.get("stripeCustomerId")
    if not cid:
        raise HTTPException(
            status_code=400,
            detail="No billing account found. Subscribe to a plan first.",
        )
    url = create_portal_session(
        customer_id=cid,
        return_url=f"{BASE_URL}/dashboard.html",
    )
    return {"redirect": url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe sends signed events here. Must be publicly reachable."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = handle_webhook(payload, sig_header)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    result = process_webhook_event(event)
    return {"received": True, "result": result}
