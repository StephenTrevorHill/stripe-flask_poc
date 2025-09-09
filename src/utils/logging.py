import json
import logging
import os
import sys
import time

_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "time": int(time.time()),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "stage": os.getenv("STAGE", "dev"),
        }
        # carry arbitrary context via "extra"
        extra = getattr(record, "extra", None)
        if extra and isinstance(extra, dict):
            base.update(extra)
        return json.dumps(base)

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())

logger = logging.getLogger("app")
logger.setLevel(_LEVEL)
logger.handlers = [_handler]
logger.propagate = False

def log(level, msg, **ctx):
    logger.log(getattr(logging, level.upper()), msg, extra={"extra": ctx})

# --- add to src/utils/logging.py ---
SENSITIVE_KEYS = {
    "client_secret", "api_key", "authorization", "password",
    "email", "phone", "address", "name", "token"
}

def _scrub_value(v):
    if isinstance(v, str):
        # redact obvious secrets in strings
        if v.startswith("whsec_") or v.startswith("sk_"):
            return "[REDACTED]"
        # cap huge strings to keep log lines small
        return v[:2000]
    return v

def scrub(obj, max_len=3500):
    """
    Recursively redact sensitive fields and trim size.
    Returns a JSON-safe structure (no pretty-print).
    """
    try:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                kl = str(k).lower()
                if kl in SENSITIVE_KEYS or "secret" in kl or "token" in kl:
                    out[k] = "[REDACTED]"
                else:
                    out[k] = scrub(v, max_len)
            return out
        if isinstance(obj, list):
            return [scrub(x, max_len) for x in obj][:50]  # avoid giant arrays
        return _scrub_value(obj)
    finally:
        # We keep total log payload small by trimming later at callsite (see payload_preview)
        pass