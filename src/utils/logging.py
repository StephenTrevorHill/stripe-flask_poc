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