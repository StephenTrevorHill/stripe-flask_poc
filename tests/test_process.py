from src.handlers import process
import json
from botocore.stub import Stubber, ANY


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
    monkeypatch.setattr(process.time, "time", lambda: 1700000000)
    stubber = Stubber(process.ddb)

    # 1) Idempotency
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.TABLE_NAME,
            "Key": {"eventId": {"S": "evt_123"}},
            "UpdateExpression": (
                "SET #s = :s, processedAt = :t, #type = :type, "
                "tenantId = :tenant, createdAt = :created"
            ),
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

    # 2) Payment summary
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.TABLE_NAME,
            "Key": {"eventId": {"S": "payment#pi_1"}},
            "UpdateExpression": "SET entity=:e, orderId=:o, paymentId=:p, #s=:s, amountCents=:amt, lastUpdatedAt=:t",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {
                ":e": {"S": "PAYMENT"},
                ":o": {"S": "order_42"},
                ":p": {"S": "pi_1"},
                ":s": {"S": "SUCCEEDED"},
                ":amt": {"N": "5000"},
                ":t": {"S": "1700000000"},
            },
        },
    )

    # 3) Order bump
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.TABLE_NAME,
            "Key": {"eventId": {"S": "order#order_42"}},
            "UpdateExpression": "SET entity=:e, orderId=:o, lastUpdatedAt=:t ADD amountCents :d",
            "ExpressionAttributeValues": {
                ":e": {"S": "ORDER"},
                ":o": {"S": "order_42"},
                ":t": {"S": "1700000000"},
                ":d": {"N": "5000"},
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