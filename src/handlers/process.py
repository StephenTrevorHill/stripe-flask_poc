import json
import os
import time
import boto3

# Safe at import: default for tests, real value in Lambda env
TABLE_NAME = os.environ.get("TABLE_NAME", "events-staging")
ddb = boto3.client("dynamodb")


def apply_event(payload: dict):
    # Upsert processed status; simple example
    event_id = payload.get("id")
    if not event_id:
        raise ValueError("missing id")
    ddb.update_item(
        TableName=TABLE_NAME,
        Key={"eventId": {"S": event_id}},
        UpdateExpression="SET #s = :s, processedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": {"S": "PROCESSED"},
            ":t": {"S": str(int(time.time()))},
        },
    )


def handler(event, context):
    failures = []
    for r in event.get("Records", []):
        try:
            payload = json.loads(r["body"]) if r.get("body") else {}
            apply_event(payload)
        except Exception:
            failures.append({"itemIdentifier": r["messageId"]})
    return {"batchItemFailures": failures}