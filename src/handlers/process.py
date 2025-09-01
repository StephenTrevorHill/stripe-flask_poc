import json
import os
import time
import boto3

# Use a safe default for tests; Lambda will set TABLE_NAME in env
TABLE_NAME = os.environ.get("TABLE_NAME", "events-staging")
ddb = boto3.client("dynamodb")


def _now_str():
    return str(int(time.time()))


def _get_tenant_and_created(payload: dict):
    tenant = (
        payload.get("account")
        or (payload.get("data") or {}).get("object", {}).get("account")
        or "demo"
    )
    created = str(payload.get("created") or int(time.time()))
    return tenant, created


def _int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _amount_from_object(obj: dict, evt_type: str) -> int:
    """Return amount in Stripe's smallest unit (already cents for USD)."""
    if evt_type == "payment_intent.succeeded":
        return _int(obj.get("amount_received") or obj.get("amount"))
    if evt_type == "payment_intent.payment_failed":
        return 0
    if evt_type == "charge.refunded":
        return -abs(_int(obj.get("amount_refunded") or obj.get("amount")))
    return _int(obj.get("amount_received") or obj.get("amount") or 0)


def _mark_processed_once(payload: dict):
    """Idempotency guard + basic metadata upsert. First caller wins; duplicates skip."""
    event_id = payload.get("id")
    if not event_id:
        raise ValueError("missing id")
    tenant, created = _get_tenant_and_created(payload)
    now = _now_str()

    ddb.update_item(
        TableName=TABLE_NAME,
        Key={"eventId": {"S": event_id}},
        UpdateExpression=(
            "SET #s = :s, processedAt = :t, #type = :type, "
            "tenantId = :tenant, createdAt = :created"
        ),
        ConditionExpression="attribute_not_exists(processedAt)",
        ExpressionAttributeNames={"#s": "status", "#type": "type"},
        ExpressionAttributeValues={
            ":s": {"S": "PROCESSED"},
            ":t": {"S": now},
            ":type": {"S": payload.get("type", "")},
            ":tenant": {"S": tenant},
            ":created": {"S": created},
        },
    )


def _upsert_payment_summary(order_id: str, payment_id: str, status: str, amount_cents: int):
    now = _now_str()
    ddb.update_item(
        TableName=TABLE_NAME,
        Key={"eventId": {"S": f"payment#{payment_id}"}},
        UpdateExpression=(
            "SET entity=:e, orderId=:o, paymentId=:p, #s=:s, amountCents=:amt, lastUpdatedAt=:t"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":e": {"S": "PAYMENT"},
            ":o": {"S": order_id},
            ":p": {"S": payment_id},
            ":s": {"S": status},
            ":amt": {"N": str(int(amount_cents))},
            ":t": {"S": now},
        },
    )


def _bump_order_totals(order_id: str, delta_cents: int):
    now = _now_str()
    ddb.update_item(
        TableName=TABLE_NAME,
        Key={"eventId": {"S": f"order#{order_id}"}},
        UpdateExpression="SET entity=:e, orderId=:o, lastUpdatedAt=:t ADD amountCents :d",
        ExpressionAttributeValues={
            ":e": {"S": "ORDER"},
            ":o": {"S": order_id},
            ":t": {"S": now},
            ":d": {"N": str(int(delta_cents))},
        },
    )


def _update_business_state(payload: dict):
    evt_type = payload.get("type", "")
    obj = (payload.get("data") or {}).get("object") or {}
    order_id = (
        (obj.get("metadata") or {}).get("order_id")
        or obj.get("order_id")
        or "unknown"
    )
    payment_id = obj.get("id") or obj.get("payment_intent") or "unknown"
    amount_cents = _amount_from_object(obj, evt_type)

    if evt_type == "payment_intent.succeeded":
        _upsert_payment_summary(order_id, payment_id, "SUCCEEDED", amount_cents)
        _bump_order_totals(order_id, amount_cents)
    elif evt_type == "payment_intent.payment_failed":
        _upsert_payment_summary(order_id, payment_id, "FAILED", 0)
    elif evt_type == "charge.refunded":
        _upsert_payment_summary(order_id, payment_id, "REFUNDED", -abs(amount_cents))
        _bump_order_totals(order_id, amount_cents)  # amount_cents is negative here
    else:
        # No-op for unhandled types; still recorded by _mark_processed_once
        pass


def handler(event, context):
    failures = []
    for r in event.get("Records", []):
        try:
            payload = json.loads(r.get("body") or "{}")
            # 1) Idempotency guard
            try:
                _mark_processed_once(payload)
            except ddb.exceptions.ConditionalCheckFailedException:
                continue  # already processed; skip silently

            # 2) Business effects
            apply_event(payload)

        except Exception:
            failures.append({"itemIdentifier": r.get("messageId")})
    return {"batchItemFailures": failures}

def apply_event(payload: dict):
    """Public entrypoint for business logic (kept so tests can monkeypatch)."""
    _update_business_state(payload)