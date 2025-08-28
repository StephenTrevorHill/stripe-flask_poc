import os
import json
import hmac
import hashlib
import time
from botocore.stub import Stubber
from src.handlers import ingest

def make_sig(payload: str, secret: str):
    t = str(int(time.time()))
    v1 = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"

def test_ingest_uses_expected_ddb_and_sqs_calls(monkeypatch):
    os.environ["TABLE_NAME"] = "events-staging"
    os.environ["QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123/events-staging"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

    payload = json.dumps({
        "id": "evt_123",
        "created": 111,
        "data": {"object": {"account": "t_demo"}}
    })
    sig = make_sig(payload, os.environ["STRIPE_WEBHOOK_SECRET"])

    # Stub DynamoDB put_item (idempotent create)
    ddb_stubber = Stubber(ingest.ddb)
    ddb_stubber.add_response(
        "put_item",
        expected_params={
            "TableName": "events-staging",
            "Item": {
                "eventId": {"S": "evt_123"},
                "tenantId": {"S": "t_demo"},
                "createdAt": {"S": "111"},
                "status": {"S": "QUEUED"},
                "schemaVersion": {"N": "1"},
            },
            "ConditionExpression": "attribute_not_exists(eventId)",
        },
        service_response={},
    )

    # Stub SQS send_message
    sqs_stubber = Stubber(ingest.sqs)
    sqs_stubber.add_response(
        "send_message",
        expected_params={
            "QueueUrl": os.environ["QUEUE_URL"],
            "MessageBody": payload,
            "MessageAttributes": {
                "tenantId": {"DataType": "String", "StringValue": "t_demo"},
                "externalEventId": {"DataType": "String", "StringValue": "evt_123"},
            },
        },
        service_response={"MessageId": "m-1"},
    )

    with ddb_stubber, sqs_stubber:
        event = {"body": payload, "headers": {"Stripe-Signature": sig}}
        res = ingest.handler(event, None)
        assert res["statusCode"] == 200
