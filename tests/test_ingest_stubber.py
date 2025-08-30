# tests/test_ingest_stubber.py
import os, json, hmac, hashlib, time
from botocore.stub import Stubber
from src.handlers import ingest

def make_sig(payload: str, secret: str):
    t = str(int(time.time()))
    v1 = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"

def test_ingest_sends_only_sqs(monkeypatch):
    os.environ["QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123/events-staging"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    payload = json.dumps({"id": "evt_123", "created": 111})
    sig = make_sig(payload, os.environ["STRIPE_WEBHOOK_SECRET"])

    # Stub SQS send_message (the only AWS call now)
    sqs_stubber = Stubber(ingest.sqs)
    sqs_stubber.add_response(
        "send_message",
        expected_params={
            "QueueUrl": os.environ["QUEUE_URL"],
            "MessageBody": payload,
        },
        service_response={"MessageId": "m-1"},
    )

    with sqs_stubber:
        event = {"body": payload, "headers": {"Stripe-Signature": sig}}
        res = ingest.handler(event, None)
        assert res["statusCode"] == 200