# app/webhooks/routes.py

# import os
import json
import uuid
from flask import Blueprint, current_app, request, jsonify
import stripe
from ..extensions import db
from ..models import Payment, PaymentEvent, PaymentStatus, Order, OrderStatus
from sqlalchemy import func


webhooks_bp = Blueprint("webhooks", __name__)

@webhooks_bp.post("/stripe")
def stripe_webhook():
    # Configure Stripe client (safe in request scope)
    stripe.api_key = current_app.config.get("STRIPE_API_KEY", "")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")

    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret,
        )
    except Exception as e:
        current_app.logger.warning(f"webhook signature or payload error: {e}")
        return jsonify({"error": "invalid"}), 400

    # Idempotency guard: record/skip on duplicate event
    evt_id = event.get("id")
    evt_type = event.get("type")

    existing_evt = PaymentEvent.query.filter_by(stripe_event_id=evt_id).first()
    if existing_evt:
        # Already processed; return 200 so Stripe won't retry
        return "", 200

    # Store raw event
    pe = PaymentEvent(
        id=str(uuid.uuid4()),
        stripe_event_id=evt_id,
        type=evt_type,
        payload=json.dumps(event)[:1_000_000],  # bound size
    )
    db.session.add(pe)

    # Handle a subset of key events
    obj = event.get("data", {}).get("object", {})

    # We want to normalize onto Payment Intent when possible
    # Some events deliver 'payment_intent' nested under charge or session.
    payment_intent_id = None
    currency = None
    amount_received = 0
    status = None
    method_type = None
    card = {}

    if evt_type.startswith("payment_intent."):
        payment_intent_id = obj.get("id")
        currency = obj.get("currency")
        amount_received = obj.get("amount_received", 0) or 0
        status = obj.get("status")
        # Pull payment method details if available
        pm = obj.get("charges", {}).get("data", [{}])
        if pm and isinstance(pm, list) and pm[0].get("payment_method_details"):
            pmd = pm[0]["payment_method_details"]
            method_type = pmd.get("type")
            card = pmd.get("card", {}) if method_type == "card" else {}
    elif evt_type.startswith("charge."):
        payment_intent_id = obj.get("payment_intent")
        currency = obj.get("currency")
        amount_received = obj.get("amount", 0) or 0
        status = "succeeded" if obj.get("paid") and obj.get("status") == "succeeded" else obj.get("status")
        pmd = obj.get("payment_method_details", {})
        method_type = pmd.get("type")
        card = pmd.get("card", {}) if method_type == "card" else {}
    elif evt_type == "checkout.session.completed":
        # session contains payment_intent
        payment_intent_id = obj.get("payment_intent")
        currency = obj.get("currency")
        # amount_total may be on session, but we'll re-sync from PI if needed
        amount_received = obj.get("amount_total", 0) or 0
        status = "succeeded"  # completed
        method_type = None

    # Map Stripe status to enum if possible
    status_enum_map = {
        "requires_payment_method": PaymentStatus.REQUIRES_PAYMENT_METHOD,
        "requires_confirmation": PaymentStatus.REQUIRES_CONFIRMATION,
        "processing": PaymentStatus.PROCESSING,
        "succeeded": PaymentStatus.SUCCEEDED,
        "canceled": PaymentStatus.CANCELED,
        "requires_action": PaymentStatus.REQUIRES_ACTION,
    }
    status_enum = status_enum_map.get((status or "").lower(), PaymentStatus.PROCESSING)

    if payment_intent_id:
        # Upsert Payment by PI id
        payment = Payment.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
        if not payment:
            payment = Payment(
                id=str(uuid.uuid4()),
                stripe_payment_intent_id=payment_intent_id,
                currency=currency or "usd",
                amount_received=amount_received or 0,
                status=status_enum,
            )
            # Attempt to link to Order via metadata.order_id (if available)
            # To do that we may need to fetch the PI if metadata isn't in the event.
            order_id = None
            # Some events include metadata directly
            metadata = obj.get("metadata") or {}
            order_id = metadata.get("order_id")

            # If we don't have it but we do have the PI id, try to retrieve the PI
            try:
                if not order_id and payment_intent_id and current_app.config.get("STRIPE_API_KEY"):
                    pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                    if pi and pi.get("metadata"):
                        order_id = pi["metadata"].get("order_id")
            except Exception as e:
                current_app.logger.info(f"PI retrieve failed or unnecessary: {e}")

            if order_id:
                payment.order_id = order_id

            db.session.add(payment)
        else:
            # Update fields if we learned more
            payment.currency = currency or payment.currency
            payment.amount_received = max(payment.amount_received or 0, amount_received or 0)
            payment.status = status_enum or payment.status

        # Attach some card details when present
        if card:
            payment.method_type = "card"
            payment.card_brand = card.get("brand")
            payment.card_last4 = card.get("last4")
            payment.card_exp_month = card.get("exp_month")
            payment.card_exp_year = card.get("exp_year")

        # Link event to payment
        pe.payment_id = payment.id


        # If linked to an order, recompute order status from all succeeded payments
        if payment.order_id:
            order = Order.query.filter_by(id=payment.order_id).first()
            if order:
                total_paid = _recompute_order_status(order)
            current_app.logger.info(f"order {order.id}: total_paid={total_paid} / amount_due={order.amount_due} -> {order.status}"
        )

        # # If we can find the order, consider updating status
        # if payment.order_id and payment.status == PaymentStatus.SUCCEEDED:
        #     order = Order.query.filter_by(id=payment.order_id).first()
        #     if order:
        #         order.status = order.status or "PAID"

    else:
        current_app.logger.info(f"Unhandled or non-PI event type: {evt_type}")

    db.session.commit()
    return "", 200

def _recompute_order_status(order):
    """Recalculate order.status from all SUCCEEDED payments (minor units)."""
    total_paid = (
        db.session.query(func.coalesce(func.sum(Payment.amount_received), 0))
        .filter(
            Payment.order_id == order.id,
            Payment.status == PaymentStatus.SUCCEEDED,
        )
        .scalar()
    ) or 0

    if total_paid == 0:
        order.status = OrderStatus.AWAITING_PAYMENT
    elif total_paid < (order.amount_due or 0):
        order.status = OrderStatus.PARTIALLY_PAID
    else:
        order.status = OrderStatus.PAID

    return total_paid