import json
from unittest.mock import patch
from app.extensions import db
from app.models import PaymentEvent, Payment, PaymentStatus

def make_event(evt_id="evt_1", evt_type="payment_intent.succeeded", pi_id="pi_123", currency="usd", amount=1234):
    return {
        "id": evt_id,
        "type": evt_type,
        "data": {
            "object": {
                "id": pi_id,
                "currency": currency,
                "amount_received": amount,
                "status": "succeeded",
                "charges": {"data": []},
                "metadata": {"order_id": "order_abc"},
            }
        }
    }

@patch("stripe.Webhook.construct_event")
def test_idempotent_processing(mock_construct, client, app):
    # First delivery
    event = make_event(evt_id="evt_A", pi_id="pi_A")
    mock_construct.return_value = event

    resp = client.post("/webhooks/stripe", data=json.dumps(event), headers={"Stripe-Signature": "t=0,v1=deadbeef"})
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.query(PaymentEvent).count() == 1
        assert db.session.query(Payment).count() == 1
        p = db.session.query(Payment).first()
        assert p.status == PaymentStatus.SUCCEEDED
        assert p.stripe_payment_intent_id == "pi_A"

    # Duplicate delivery (same event id)
    mock_construct.return_value = event
    resp2 = client.post("/webhooks/stripe", data=json.dumps(event), headers={"Stripe-Signature": "t=0,v1=deadbeef"})
    assert resp2.status_code == 200

    with app.app_context():
        # No additional rows
        assert db.session.query(PaymentEvent).count() == 1
        assert db.session.query(Payment).count() == 1
