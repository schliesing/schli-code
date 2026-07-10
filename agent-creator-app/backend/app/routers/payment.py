"""
Payment router: Stripe Checkout integration for agent downloads.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.agent import Agent, AgentExport, PaymentIntent
from app.schemas.agent import CheckoutResponse, PaymentStatusResponse

router = APIRouter(prefix="/api/payment", tags=["payment"])

EXPORT_TOKEN_TTL_HOURS = 24


def _get_stripe():
    """Initialize Stripe with the configured secret key."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sistema de pagamento não configurado. "
                "Configure a variável STRIPE_SECRET_KEY no servidor."
            ),
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


@router.post("/create-checkout", response_model=CheckoutResponse)
def create_checkout_session(
    body: dict,
    db: Session = Depends(get_db),
):
    """
    Creates a Stripe Checkout Session for downloading an agent package.

    Request body:
        agent_id: str
        session_id: str  (user session for auth)
        success_url: str (redirect after payment)
        cancel_url: str  (redirect if payment cancelled)
    """
    agent_id = body.get("agent_id", "")
    session_id = body.get("session_id", "")
    success_url = body.get("success_url", f"{settings.FRONTEND_URL}/success")
    cancel_url = body.get("cancel_url", f"{settings.FRONTEND_URL}/cancel")

    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id é obrigatório.")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id é obrigatório.")

    # Verify agent exists and belongs to session
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    if agent.session_id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para comprar este agente.",
        )

    _stripe = _get_stripe()

    agent_name = agent.name or "Agente IA"
    description = f"Pacote de download do agente: {agent_name}"

    try:
        checkout_session = _stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {
                            "name": f"Agente IA: {agent_name}",
                            "description": description,
                            "images": [],
                        },
                        "unit_amount": settings.PRICE_CENTS,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "agent_id": agent_id,
                "user_session_id": session_id,
            },
            locale="pt-BR",
        )
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao criar sessão de pagamento: {str(e)}",
        )

    # Record the payment intent
    pi_record = PaymentIntent(
        id=checkout_session.id,  # Using checkout session ID as the record ID
        agent_id=agent_id,
        session_id=session_id,
        amount_cents=settings.PRICE_CENTS,
        currency="brl",
        status="pending",
    )
    db.add(pi_record)
    db.commit()

    return CheckoutResponse(
        checkout_url=checkout_session.url,
        session_id=checkout_session.id,
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Stripe webhook endpoint.
    Handles checkout.session.completed events to grant download access.
    """
    payload = await request.body()

    _stripe = _get_stripe()

    # Verify webhook signature
    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = _stripe.Webhook.construct_event(
                payload,
                stripe_signature or "",
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except stripe.SignatureVerificationError:
            raise HTTPException(
                status_code=400,
                detail="Assinatura do webhook inválida.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao processar webhook: {str(e)}",
            )
    else:
        # Development mode: parse without signature verification
        import json
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Payload inválido.")

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        checkout_session = event["data"]["object"]
        metadata = checkout_session.get("metadata", {})
        agent_id = metadata.get("agent_id", "")
        user_session_id = metadata.get("user_session_id", "")
        stripe_session_id = checkout_session.get("id", "")
        payment_status = checkout_session.get("payment_status", "")

        if payment_status == "paid" and agent_id:
            # Update payment intent status
            pi = db.query(PaymentIntent).filter(PaymentIntent.id == stripe_session_id).first()
            if pi:
                pi.status = "completed"
                db.commit()

            # Check if a download token already exists for this payment
            existing = (
                db.query(AgentExport)
                .filter(AgentExport.payment_id == stripe_session_id)
                .first()
            )
            if not existing:
                # Create download token
                token = secrets.token_urlsafe(32)
                expires_at = datetime.now(timezone.utc) + timedelta(hours=EXPORT_TOKEN_TTL_HOURS)

                export_record = AgentExport(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    payment_id=stripe_session_id,
                    download_token=token,
                    expires_at=expires_at,
                )
                db.add(export_record)
                db.commit()

    elif event_type == "payment_intent.payment_failed":
        pi_data = event["data"]["object"]
        pi_id = pi_data.get("id", "")
        pi = db.query(PaymentIntent).filter(PaymentIntent.id == pi_id).first()
        if pi:
            pi.status = "failed"
            db.commit()

    return {"received": True, "event_type": event_type}


@router.get("/status/{agent_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    agent_id: str,
    session_id: str,
    db: Session = Depends(get_db),
):
    """
    Check if an agent has been paid for and has an available download token.

    Query params:
        session_id: str (user session for auth)
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    if agent.session_id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para verificar este agente.",
        )

    now = datetime.now(timezone.utc)

    # Look for a valid (not-yet-used, not-expired) export token
    valid_export = (
        db.query(AgentExport)
        .filter(
            AgentExport.agent_id == agent_id,
            AgentExport.downloaded_at.is_(None),
            AgentExport.expires_at > now,
        )
        .order_by(AgentExport.created_at.desc())
        .first()
    )

    if valid_export:
        return PaymentStatusResponse(
            agent_id=agent_id,
            paid=True,
            download_token=valid_export.download_token,
            expires_at=valid_export.expires_at,
        )

    return PaymentStatusResponse(
        agent_id=agent_id,
        paid=False,
        download_token=None,
        expires_at=None,
    )
