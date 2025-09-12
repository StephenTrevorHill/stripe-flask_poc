from src.handlers import process
import json
from botocore.stub import Stubber, ANY
from botocore.exceptions import ClientError  # noqa: F401


import os
os.environ.setdefault("EVENTS_TABLE", "events-staging")
os.environ.setdefault("PAYMENTS_TABLE", "payments-staging")
os.environ.setdefault("ORDERS_TABLE", "orders-staging")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

class Boom(Exception):
    pass


def test_process_partial_batch(monkeypatch):
    def ok_apply(payload): return None
    def bad_apply(payload): raise Boom("fail")

    # 🔧 disable the DynamoDB idempotency write for this test
    monkeypatch.setattr(process, "_mark_processed_once", lambda payload: None)

    # keep your existing monkeypatch that simulates per-record success/failure
    monkeypatch.setattr(
        process, "apply_event",
        lambda p: ok_apply(p) if p.get("id") == "ok" else bad_apply(p)
    )

    event = {
        "Records": [
            {"messageId": "m1", "body": "{\"id\": \"ok\"}"},
            {"messageId": "m2", "body": "{\"id\": \"bad\"}"},
        ]
    }

    res = process.handler(event, None)
    assert res["batchItemFailures"] == [{"itemIdentifier": "m2"}]

# --- appended business-logic tests ---
def test_payment_intent_succeeded_updates_payment_and_order(monkeypatch):
    # Freeze time for deterministic values
    monkeypatch.setattr(process.time, "time", lambda: 1700000000)

    stubber = Stubber(process.ddb)

    # 1) Idempotency marker in EVENTS_TABLE
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.EVENTS_TABLE,
            "Key": {"eventId": {"S": "evt_123"}},
            "UpdateExpression": ANY,  # avoid whitespace sensitivity
            "ConditionExpression": "attribute_not_exists(processedAt)",
            "ExpressionAttributeNames": {"#s": "status", "#type": "type"},
            "ExpressionAttributeValues": {
                ":s": {"S": "PROCESSED"},
                ":t": {"S": "1700000000"},
                ":type": {"S": "payment_intent.succeeded"},
                ":tenant": {"S": ANY},
                ":created": {"S": ANY},
            },
        },
    )

    # 2) Payment summary in PAYMENTS_TABLE (key: paymentId)
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.PAYMENTS_TABLE,
            "Key": {"paymentId": {"S": "pi_1"}},
            "UpdateExpression": ANY,
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {
                ":o": {"S": "order_42"},
                ":s": {"S": "SUCCEEDED"},
                ":a": {"N": "5000"},
                ":t": {"S": "1700000000"},
            },
        },
    )

    # 3a) Order bump (ADD amountReceivedCents ... ReturnValues=ALL_NEW)
    stubber.add_response(
        "update_item",
        service_response={
            # The handler reads these to compute status
            "Attributes": {
                "amountReceivedCents": {"N": "5000"},
                "orderTotalCents": {"N": "5000"},  # make total==received so status -> "paid"
            }
        },
        expected_params={
            "TableName": process.ORDERS_TABLE,
            "Key": {"orderId": {"S": "order_42"}},
            "UpdateExpression": ANY,  # e.g., "SET updatedAt=:t, createdAt=if_not_exists(createdAt, :t) ADD amountReceivedCents :d"
            "ExpressionAttributeValues": {
                ":t": {"S": "1700000000"},
                ":d": {"N": "5000"},
            },
            "ReturnValues": "ALL_NEW",
        },
    )

    # 3b) Status set based on snapshot (paid/partial/pending)
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.ORDERS_TABLE,
            "Key": {"orderId": {"S": "order_42"}},
            "UpdateExpression": ANY,  # "SET #s=:s, updatedAt=:t"
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {
                ":s": {"S": "paid"},
                ":t": {"S": "1700000000"},
            },
        },
    )
    

    payload = {
        "id": "evt_123",
        "type": "payment_intent.succeeded",
        "created": 1700000000,
        "data": {"object": {"id": "pi_1", "metadata": {"order_id": "order_42"}, "amount_received": 5000}},
    }

    with stubber:
        res = process.handler({"Records": [{"messageId": "m1", "body": json.dumps(payload)}]}, None)
        assert res["batchItemFailures"] == []

def test_duplicate_event_is_skipped(monkeypatch):
    stubber = Stubber(process.ddb)
    stubber.add_client_error(
        "update_item",
        service_error_code="ConditionalCheckFailedException",
        service_message="Already processed",
        http_status_code=400,
    )
    payload = {"id": "evt_123", "type": "payment_intent.succeeded"}
    with stubber:
        res = process.handler({"Records": [{"messageId": "m1", "body": json.dumps(payload)}]}, None)
        assert res["batchItemFailures"] == []