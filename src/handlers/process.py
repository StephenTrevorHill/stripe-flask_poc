# src/handlers/process.py
import json
import os
import time
import boto3
from botocore.exceptions import ClientError
from src.utils.logging import log, scrub

ddb = boto3.client("dynamodb")

IS_VERBOSE = os.environ.get("STAGE") != "prod" or os.environ.get("LOG_LEVEL", "").upper() == "DEBUG"

# env (must be set by Lambda / tests before import)
EVENTS_TABLE   = os.environ["EVENTS_TABLE"]   # idempotency + raw event marker
PAYMENTS_TABLE = os.environ["PAYMENTS_TABLE"] # payment summaries
ORDERS_TABLE   = os.environ["ORDERS_TABLE"]   # order aggregates
STAGE          = os.environ.get("STAGE", "staging")

def _now_s() -> str:
    return str(int(time.time()))

def _mark_processed_once(payload: dict) -> None:
    """
    Idempotency gate: write a processed marker for the Stripe event.
    Condition fails (CCF) if we've seen it already.
    """
    evt_id = payload.get("id") or payload.get("event", {}).get("id")
    if not evt_id:
        raise ValueError("missing event id")

    ddb.update_item(
        TableName=EVENTS_TABLE,
        Key={"eventId": {"S": evt_id}},
        # keep spaces around '=' to satisfy strict Stubber expectations in tests
        UpdateExpression="SET #s = :s, processedAt = :t, #type = :type, tenantId = :tenant, createdAt = :created",
        ConditionExpression="attribute_not_exists(processedAt)",
        ExpressionAttributeNames={"#s": "status", "#type": "type"},
        ExpressionAttributeValues={
            ":s": {"S": "PROCESSED"},
            ":t": {"S": _now_s()},
            ":type": {"S": payload.get("type", "unknown")},
            ":tenant": {"S": STAGE},
            ":created": {"S": str(payload.get("created") or int(time.time()))},
        },
    )

def _upsert_payment_summary(pi_id: str, order_id: str, status: str, amount_cents: int) -> None:
    ddb.update_item(
        TableName=PAYMENTS_TABLE,
        Key={"paymentId": {"S": pi_id}},
        UpdateExpression="SET orderId=:o, #s=:s, amountCents=:a, updatedAt=:t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":o": {"S": order_id},
            ":s": {"S": status},
            ":a": {"N": str(amount_cents)},
            ":t": {"S": _now_s()},
        },
    )

def _order_add_amount(order_id: str, status: str, delta_cents: int) -> None:
    ddb.update_item(
        TableName=ORDERS_TABLE,
        Key={"orderId": {"S": order_id}},
        UpdateExpression="SET #s=:s, updatedAt=:t ADD amountCents :d",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": {"S": status},
            ":t": {"S": _now_s()},
            ":d": {"N": str(delta_cents)},
        },
    )

def apply_event(payload: dict) -> None:
    """
    Business logic per Stripe event type.
    Extend with other types as needed.
    """
    etype = payload.get("type")
    if etype == "payment_intent.succeeded":
        obj = payload["data"]["object"]
        pi_id = obj["id"]
        order_id = obj.get("metadata", {}).get("order_id", "unknown")
        amount = obj.get("amount_received", 0) or obj.get("amount", 0)

        _upsert_payment_summary(pi_id, order_id, "SUCCEEDED", amount)
        received, total, status = _order_apply_payment(order_id, amount)
        log("info", "payment_succeeded",
            paymentId=pi_id, orderId=order_id, amount=amount,
            orderTotal=total, amountReceived=received, orderStatus=status)

    elif etype == "payment_intent.payment_failed":
        obj = payload["data"]["object"]
        pi_id = obj["id"]
        order_id = obj.get("metadata", {}).get("order_id", "unknown")

        _upsert_payment_summary(pi_id, order_id, "FAILED", 0)
        _order_add_amount(order_id, "unpaid", 0)
        log("warn", "payment_failed", paymentId=pi_id, orderId=order_id)

    else:
        # Unknown/ignored event types are a no-op
        log("debug", "event_ignored", type=etype, eventId=payload.get("id"))

def handler(event, context):
    failures = []

    log("debug", "this_is_debug", extra={"ctx": {"sample": True}})

    for rec in event.get("Records", []):
        mid = rec.get("messageId")
        try:
            payload = json.loads(rec["body"])

            if IS_VERBOSE:
                obj = (payload.get("data") or {}).get("object") or {}
                log("debug", "process_dequeued",
                    messageId=mid, eventId=payload.get("id"), type=payload.get("type"),
                    orderId=(obj.get("metadata") or {}).get("order_id"),
                    paymentId=obj.get("id"),
                    payload_preview=scrub(payload))

            # test hook: force a failure if metadata.force_fail=1
            obj = (payload.get("data") or {}).get("object") or {}
            meta = obj.get("metadata") or {}
            if meta.get("force_fail") == "1":
                raise RuntimeError("forced failure for DLQ test")

            # idempotency: skip duplicates without failing the batch item
            try:
                _mark_processed_once(payload)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code")
                if code == "ConditionalCheckFailedException":
                    log("info", "duplicate_event_skipped", messageId=mid, eventId=payload.get("id"))
                    continue
                raise

            # business logic
            apply_event(payload)

            if IS_VERBOSE:
                log("debug", "process_applied", messageId=mid, eventId=payload.get("id"))

        except Exception as e:
            log("error", "process_failed", messageId=mid, error=str(e))
            failures.append({"itemIdentifier": mid})

    return {"batchItemFailures": failures}

def _order_apply_payment(order_id: str, delta_cents: int):
    """
    Atomically add delta_cents to amountReceivedCents, then compute and set status.
    Returns (received, total, status).
    """
    now = _now_s()

    # 1) Increment and fetch the new snapshot
    resp = ddb.update_item(
        TableName=ORDERS_TABLE,
        Key={"orderId": {"S": order_id}},
        UpdateExpression="SET updatedAt=:t, createdAt=if_not_exists(createdAt, :t) ADD amountReceivedCents :d",
        ExpressionAttributeValues={
            ":t": {"S": now},
            ":d": {"N": str(delta_cents)},
        },
        ReturnValues="ALL_NEW",
    )

    attrs = resp.get("Attributes", {})
    received = int(attrs.get("amountReceivedCents", {}).get("N", "0"))
    total = int(attrs.get("orderTotalCents", {}).get("N", "0"))

    if total > 0:
        status = "paid" if received >= total else "partial"
    else:
        # No total yet → we can’t decide paid/partial; consider this pending
        status = "pending"

    # 2) Set status (idempotent)
    ddb.update_item(
        TableName=ORDERS_TABLE,
        Key={"orderId": {"S": order_id}},
        UpdateExpression="SET #s=:s, updatedAt=:t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": {"S": status}, ":t": {"S": now}},
    )

    return received, total, status