# src/utils/logging.py
import json
import os
import sys
import time

_STAGE = os.environ.get("STAGE", "dev")
_REDACT = {"authorization", "stripe-signature", "secret", "password", "token", "api_key", "apikey", "x-api-key"}

def _now_s() -> int:
    return int(time.time())

def scrub(v, redacted="***"):
    if isinstance(v, dict):
        return {k: (redacted if k.lower() in _REDACT else scrub(val, redacted)) for k, val in v.items()}
    if isinstance(v, list):
        return [scrub(x, redacted) for x in v]
    return v

def log(level: str, msg: str, **fields):
    payload = {"time": _now_s(), "level": level.upper(), "msg": msg, "logger": "app", "stage": _STAGE}
    payload.update(fields)
    try:
        print(json.dumps(payload, separators=(",", ":")), file=sys.stdout, flush=True)
    except Exception:
        # last-ditch: at least print something
        print(f"{payload}", file=sys.stdout, flush=True)