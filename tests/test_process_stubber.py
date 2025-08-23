import json
from botocore.stub import Stubber
from src.handlers import process

def test_process_partial_batch_with_stubber(monkeypatch):
    # Freeze time to make ExpressionAttributeValues deterministic
    monkeypatch.setattr(process.time, "time", lambda: 1700000000)

    stubber = Stubber(process.ddb)

    # First message succeeds (id = "ok")
    stubber.add_response(
        "update_item",
        expected_params={
            "TableName": process.TABLE_NAME,
            "Key": {"eventId": {"S": "ok"}},
            "UpdateExpression": "SET #s = :s, processedAt = :t",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {
                ":s": {"S": "PROCESSED"},
                ":t": {"S": "1700000000"},
            },
        },
        service_response={},
    )

    # Second message fails with a simulated DynamoDB error
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
