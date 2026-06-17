"""PrismRAG — Billing API routes (Stripe)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from prismrag.auth.auth import get_current_user
from prismrag.billing.stripe_client import (
    create_checkout_session,
    create_portal_session,
    handle_webhook,
    process_webhook_event,
    STRIPE_PUBLISHABLE_KEY,
)

router = APIRouter(prefix="/api/billing", tags=["Billing"])
billing_router = router  # alias used in main.py

BASE_URL = os.getenv("PRISMRAG_BASE_URL", "http://localhost:8001")


class CheckoutIn(BaseModel):
    plan: str  # starter | professional | enterprise


@router.get("/plans")
def list_plans():
    """Return plan details and Stripe publishable key for frontend."""
    return {
        "stripePublishableKey": STRIPE_PUBLISHABLE_KEY,
        "plans": [
            {
                "id":          "free",
                "name":        "Free",
                "price":       0,
                "currency":    "usd",
                "interval":    "month",
                "description": "Try PrismRAG with no commitment",
                "features": [
                    "5,000 chunks / month",
                    "1 workspace",
                    "Graph RAG retrieval",
                    "Community support",
                ],
                "cta": "Start Free",
            },
            {
                "id":          "starter",
                "name":        "Starter",
                "price":       4900,
                "currency":    "usd",
                "interval":    "month",
                "description": "For teams building their first re-mapping pipeline",
                "features": [
                    "50,000 chunks / month",
                    "1 workspace",
                    "3 mapping versions",
                    "Graph RAG retrieval",
                    "CSV / Excel / API ingestion",
                    "Email support",
                ],
                "cta": "Start Starter",
                "popular": False,
            },
            {
                "id":          "professional",
                "name":        "Professional",
                "price":       19900,
                "currency":    "usd",
                "interval":    "month",
                "description": "For teams deploying domain-specific semantic search",
                "features": [
                    "500,000 chunks / month",
                    "10 workspaces",
                    "20 mapping versions",
                    "Tier-2 MLP training",
                    "Graph RAG + Bridge vectors",
                    "SQL + chunk re-mapping",
                    "Priority support",
                    "Webhook callbacks",
                ],
                "cta": "Start Professional",
                "popular": True,
            },
            {
                "id":          "enterprise",
                "name":        "Enterprise",
                "price":       None,
                "currency":    "usd",
                "interval":    "month",
                "description": "Unlimited scale, dedicated infrastructure, SLA",
                "features": [
                    "Unlimited chunks",
                    "Unlimited workspaces",
                    "All mapping strategies",
                    "Custom model training",
                    "Dedicated infrastructure",
                    "99.9% SLA",
                    "Dedicated support engineer",
                    "Custom contracts",
                ],
                "cta": "Contact Sales",
                "popular": False,
            },
        ],
    }


@router.post("/checkout")
def create_checkout(body: CheckoutIn, user: dict = Depends(get_current_user)):
    if body.plan == "enterprise":
        return {"redirect": "mailto:sales@prismrag.io?subject=Enterprise%20Inquiry"}
    if body.plan == "free":
        return {"redirect": f"{BASE_URL}/dashboard"}

    try:
        url = create_checkout_session(
            user_id=user["id"],
            email=user["email"],
            name=user.get("fullName") or user["email"],
            plan=body.plan,
            success_url=f"{BASE_URL}/dashboard?upgrade=success",
            cancel_url=f"{BASE_URL}/pricing",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"redirect": url}


@router.post("/portal")
def billing_portal(user: dict = Depends(get_current_user)):
    cid = user.get("stripeCustomerId")
    if not cid:
        raise HTTPException(
            status_code=400,
            detail="No billing account found. Subscribe to a plan first.",
        )
    url = create_portal_session(
        customer_id=cid,
        return_url=f"{BASE_URL}/dashboard",
    )
    return {"redirect": url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe sends signed events here. Must be publicly reachable."""
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = handle_webhook(payload, sig_header)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    result = process_webhook_event(event)
    return {"received": True, "result": result}
