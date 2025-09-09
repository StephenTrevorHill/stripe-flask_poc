# src/handlers/ingest.py
import base64
import hashlib
import hmac
import json
import os
import time
import boto3
from src.utils.logging import log  # structured logger (JSON)

# Clients
_sqs = boto3.client("sqs")
_sm  = boto3.client("secretsmanager")

# Cache the secret across invocations
_SECRET_CACHE = None
_TOLERANCE_SECONDS = 300  # 5 minutes

def _get_secret() -> str:
    """
    Resolve Stripe webhook signing secret at cold start (and cache).
    Priority:
      1) STRIPE_WEBHOOK_SECRET (handy in unit tests / local)
      2) STRIPE_SECRET_ID -> Secrets Manager (staging/prod)
    """
    global _SECRET_CACHE
    if _SECRET_CACHE:
        return _SECRET_CACHE

    # 1) direct env for tests
    direct = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if direct:
        _SECRET_CACHE = direct
        return _SECRET_CACHE

    # 2) secrets manager
    sid = os.environ.get("STRIPE_SECRET_ID")
    if not sid:
        raise RuntimeError("Missing STRIPE_SECRET_ID or STRIPE_WEBHOOK_SECRET")
    resp = _sm.get_secret_value(SecretId=sid)
    # SecretString holds whsec_... text
    _SECRET_CACHE = resp["SecretString"]
    return _SECRET_CACHE

def _parse_stripe_sig_header(sig_header: str):
    """
    Parse 'Stripe-Signature' header: e.g. 't=1700000000,v1=abcdef,...'
    Returns (ts:int, v1:str) or (None, None) if invalid.
    """
    try:
        parts = dict(kv.split("=", 1) for kv in sig_header.split(","))
        return int(parts.get("t", "0")), parts.get("v1")
    except Exception:
        return None, None

def verify_stripe_signature(body_bytes: bytes, sig_header: str, secret: str, tolerance=_TOLERANCE_SECONDS) -> bool:
    """
    Compute HMAC-SHA256 of 't.payload' and compare to v1.
    Also enforce a timestamp tolerance to avoid replay.
    """
    if not sig_header:
        return False

    ts, v1 = _parse_stripe_sig_header(sig_header)
    if not ts or not v1:
        return False

    # Timestamp tolerance
    now = int(time.time())
    if abs(now - ts) > tolerance:
        return False

    payload = f"{ts}.".encode("utf-8") + body_bytes
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    # Constant-time compare
    return hmac.compare_digest(expected, v1)

def handler(event, context):
    """
    API Gateway → Lambda webhook ingestion.
    Verifies Stripe signature and enqueues the raw payload to SQS.
    """
    request_id = getattr(context, "aws_request_id", None)

    # Body as bytes for HMAC; decode once for SQS
    body = event.get("body", "") or ""
    body_bytes = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode("utf-8")
    headers = { (k or "").lower(): v for k, v in (event.get("headers") or {}).items() }
    sig = headers.get("stripe-signature")

    # Load secret (cached)
    try:
        secret = _get_secret()
    except Exception as e:
        log("error", "secret_resolve_failed", requestId=request_id, error=str(e))
        return {"statusCode": 500, "body": json.dumps({"ok": False})}

    # Verify signature
    if not verify_stripe_signature(body_bytes, sig, secret):
        log(
            "warn",
            "bad_signature",
            requestId=request_id,
            contentLength=len(body_bytes),
            hasSig=bool(sig),
        )
        return {"statusCode": 401, "body": "bad signature"}

    # Enqueue raw payload
    try:
        resp = _sqs.send_message(
            QueueUrl=os.environ["QUEUE_URL"],
            MessageBody=body_bytes.decode("utf-8"),
        )
        log(
            "info",
            "ingest_enqueued",
            requestId=request_id,
            contentLength=len(body_bytes),
            messageId=resp.get("MessageId"),
        )
        return {"statusCode": 200, "body": json.dumps({"ok": True})}
    except Exception as e:
        # Let Stripe retry if we couldn't enqueue
        log("error", "enqueue_failed", requestId=request_id, error=str(e))
        return {"statusCode": 500, "body": json.dumps({"ok": False})}