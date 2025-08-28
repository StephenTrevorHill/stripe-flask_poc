import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import boto3

# Create clients at import (fine for tests; we stub/monkeypatch these)
sqs = boto3.client("sqs")
ddb = boto3.client("dynamodb")

def get_cfg():
    """Load required settings at runtime, with safe defaults for tests."""
    q = os.environ.get("QUEUE_URL")                     # required in real runs
    t = os.environ.get("TABLE_NAME", "events-staging")  # harmless default for tests
    s = os.environ.get("STRIPE_WEBHOOK_SECRET", "test_secret")
    if q is None:
        # Avoid import-time KeyError; raise a clear runtime error instead.
        raise RuntimeError("Missing required env var: QUEUE_URL")
    return {"QUEUE_URL": q, "TABLE_NAME": t, "STRIPE_SECRET": s}


def verify_stripe_signature(payload_bytes: bytes, sig_header: str, secret: str, tolerance: int = 300) -> bool:
    """Minimal Stripe-style verifier: 't=timestamp,v1=signature' where v1 = HMAC_SHA256(secret, f'{t}.{payload}')."""
    if not sig_header:
        return False
    parts = dict(kv.split("=", 1) for kv in sig_header.split(",") if "=" in kv)
    t, v1 = parts.get("t"), parts.get("v1")
    if not t or not v1:
        return False
    signed = f"{t}.{payload_bytes.decode('utf-8')}".encode("utf-8")
    mac = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    try:
        ts = int(t)
        # Optional tolerance check; keep permissive in POC
        _ = abs(int(time.time()) - ts)
    except Exception:
        pass
    return hmac.compare_digest(mac, v1)


def handler(event, context):
    cfg = get_cfg()

    body = event.get("body") or ""
    body_bytes = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("utf-8")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    sig = headers.get("stripe-signature")

    if not verify_stripe_signature(body_bytes, sig, cfg["STRIPE_SECRET"]):
        print(json.dumps({"level": "warn", "msg": "bad_sig"}), flush=True)
        return {"statusCode": 401, "body": "bad signature"}

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        payload = {}

    external_event_id = payload.get("id") or str(uuid.uuid4())
    tenant_id = (
        payload.get("data", {}).get("object", {}).get("account")
        or payload.get("account")
        or "demo"
    )
    created = str(payload.get("created") or int(time.time()))
    event_id = external_event_id  # use Stripe id as our pk for idempotency

    # Idempotent create (no overwrite if already present)
    try:
        ddb.put_item(
            TableName=cfg["TABLE_NAME"],
            Item={
                "eventId": {"S": event_id},
                "tenantId": {"S": tenant_id},
                "createdAt": {"S": created},
                "status": {"S": "QUEUED"},
                "schemaVersion": {"N": "1"},
            },
            ConditionExpression="attribute_not_exists(eventId)",
        )
    except ddb.exceptions.ConditionalCheckFailedException:
        pass

    sqs.send_message(
        QueueUrl=cfg["QUEUE_URL"],
        MessageBody=body_bytes.decode("utf-8"),
        MessageAttributes={
            "tenantId": {"DataType": "String", "StringValue": tenant_id},
            "externalEventId": {"DataType": "String", "StringValue": external_event_id},
        },
    )

    print(json.dumps({"level": "info", "msg": "enqueued", "eventId": event_id, "tenantId": tenant_id}), flush=True)
    return {"statusCode": 200, "body": "ok"}
