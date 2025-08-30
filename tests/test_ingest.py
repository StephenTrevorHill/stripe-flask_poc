# tests/test_ingest.py
import json
import hmac
import hashlib
import time
import os
from src.handlers import ingest

class FakeSQS:
    def __init__(self):
        self.sent = []
    def send_message(self, **kw):
        self.sent.append(kw)
        return {"MessageId": "m-1"}

def make_sig(payload: str, secret: str):
    t = str(int(time.time()))
    signed = f"{t}.{payload}".encode("utf-8")
    v1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"

def test_ingest_signature_and_enqueue(monkeypatch):
    os.environ["QUEUE_URL"] = "https://sqs.example/q"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    sqs = FakeSQS()
    monkeypatch.setattr(ingest, "sqs", sqs)

    payload = json.dumps({"id": "evt_123", "created": 111, "data": {"object": {"account": "t_demo"}}})
    sig = make_sig(payload, os.environ["STRIPE_WEBHOOK_SECRET"])

    event = {"body": payload, "headers": {"Stripe-Signature": sig}}
    res = ingest.handler(event, None)

    assert res["statusCode"] == 200
    assert sqs.sent and sqs.sent[0]["MessageBody"] == payload

def test_ingest_bad_signature(monkeypatch):
    os.environ["QUEUE_URL"] = "https://sqs.example/q"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    sqs = FakeSQS()
    monkeypatch.setattr(ingest, "sqs", sqs)

    payload = json.dumps({"id": "evt_123"})
    event = {"body": payload, "headers": {"Stripe-Signature": "t=0,v1=bad"}}
    res = ingest.handler(event, None)

    assert res["statusCode"] == 401
    assert not sqs.sent