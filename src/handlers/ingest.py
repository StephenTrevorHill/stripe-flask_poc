# src/handlers/ingest.py
import base64
import hashlib
import hmac
import json
import os
import time
import boto3

# Single SQS client (wrapped by Stubber in tests)
sqs = boto3.client("sqs")


def get_cfg():
    """Load required settings at runtime, with safe defaults for tests."""
    q = os.environ.get("QUEUE_URL")                     # required in real runs
    s = os.environ.get("STRIPE_WEBHOOK_SECRET", "test_secret")
    if q is None:
        # Avoid import-time KeyError; raise a clear runtime error instead.
        raise RuntimeError("Missing required env var: QUEUE_URL")
    return {"QUEUE_URL": q, "STRIPE_SECRET": s}


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
        _ = abs(int(time.time()) - int(t))  # optional tolerance check
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
        print(json.dumps({"lvl": "warn", "msg": "bad_sig"}), flush=True)
        return {"statusCode": 401, "body": "bad signature"}

    # Enqueue raw payload
    sqs.send_message(
        QueueUrl=cfg["QUEUE_URL"],
        MessageBody=body_bytes.decode("utf-8"),
    )

    print(json.dumps({"lvl": "info", "msg": "enqueued"}), flush=True)
    return {"statusCode": 200, "body": "ok"}