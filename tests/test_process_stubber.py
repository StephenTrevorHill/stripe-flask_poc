from botocore.stub import Stubber, ANY
from src.handlers import process
import json

def test_process_partial_batch_with_stubber(monkeypatch):
    # Freeze time so :t matches deterministically
    monkeypatch.setattr(process.time, "time", lambda: 1700000000)

    stubber = Stubber(process.ddb)

    # First message ("ok") should succeed: match our real idempotency write
    stubber.add_response(
        "update_item",
        service_response={},
        expected_params={
            "TableName": process.TABLE_NAME,
            "Key": {"eventId": {"S": "ok"}},
            "UpdateExpression": (
                "SET #s = :s, processedAt = :t, #type = :type, "
                "tenantId = :tenant, createdAt = :created"
            ),
            "ConditionExpression": "attribute_not_exists(processedAt)",
            "ExpressionAttributeNames": {"#s": "status", "#type": "type"},
            "ExpressionAttributeValues": {
                ":s": {"S": "PROCESSED"},
                ":t": {"S": "1700000000"},
                ":type": {"S": ANY},      # don't care in this test
                ":tenant": {"S": ANY},    # derived from payload; ok to relax
                ":created": {"S": ANY},   # either payload.created or now
            },
        },
    )

    # Second message should fail with a simulated DDB error
    stubber.add_client_error(
        "update_item",
        service_error_code="InternalServerError",
        service_message="boom",
    )

    records = [
        {"messageId": "m1", "body": json.dumps({"id": "ok"})},
        {"messageId": "m2", "body": json.dumps({"id": "bad"})},
    ]

    with stubber:
        res = process.handler({"Records": records}, None)
        assert res["batchItemFailures"] == [{"itemIdentifier": "m2"}]