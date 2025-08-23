import json, hmac, hashlib, time, types, os
from src.handlers import ingest

class FakeSQS:
    def __init__(self):
        self.sent = []
    def send_message(self, **kw):
        self.sent.append(kw)
        return {"MessageId": "m-1"}

class FakeDDB:
    class exceptions:
        class ConditionalCheckFailedException(Exception):
            pass
    def __init__(self):
        self.items = {}
    def put_item(self, TableName, Item, ConditionExpression):
        k = Item["eventId"]["S"]
        if k in self.items:
            raise FakeDDB.exceptions.ConditionalCheckFailedException()
        self.items[k] = Item

def make_sig(payload: str, secret: str):
    t = str(int(time.time()))
    signed = f"{t}.{payload}".encode("utf-8")
    v1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"

def test_ingest_signature_and_enqueue(monkeypatch):
    os.environ["TABLE_NAME"] = "events-staging"
    os.environ["QUEUE_URL"] = "https://sqs.example/q"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    sqs = FakeSQS(); ddb = FakeDDB()
    monkeypatch.setattr(ingest, "sqs", sqs)
    monkeypatch.setattr(ingest, "ddb", ddb)

    payload = json.dumps({"id": "evt_123", "created": 111, "data": {"object": {"account": "t_demo"}}})
    sig = make_sig(payload, os.environ["STRIPE_WEBHOOK_SECRET"])

    event = {"body": payload, "headers": {"Stripe-Signature": sig}}
    res = ingest.handler(event, types.SimpleNamespace())

    assert res["statusCode"] == 200
    assert sqs.sent and sqs.sent[0]["MessageBody"] == payload

def test_ingest_bad_signature(monkeypatch):
    os.environ["TABLE_NAME"] = "events-staging"
    os.environ["QUEUE_URL"] = "https://sqs.example/q"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    sqs = FakeSQS(); ddb = FakeDDB()
    monkeypatch.setattr(ingest, "sqs", sqs)
    monkeypatch.setattr(ingest, "ddb", ddb)

    payload = json.dumps({"id": "evt_123"})
    event = {"body": payload, "headers": {"Stripe-Signature": "t=0,v1=bad"}}
    res = ingest.handler(event, None)

    assert res["statusCode"] == 401
    assert not sqs.sent
