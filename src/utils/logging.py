import json
import os
import sys
import time
import logging
import logging as _pylog

_STAGE = os.environ.get("STAGE", "dev")
_LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARN": logging.WARNING,
           "WARNING": logging.WARNING, "ERROR": logging.ERROR}
_REDACT = {"authorization", "stripe-signature", "secret", "password",
           "token", "api_key", "apikey", "x-api-key"}

def is_debug_enabled() -> bool:
    return _logger.isEnabledFor(_pylog.DEBUG)

def scrub(v, redacted="***"):
    if isinstance(v, dict):
        return {k: (redacted if k.lower() in _REDACT else scrub(val, redacted)) for k, val in v.items()}
    if isinstance(v, list):
        return [scrub(x, redacted) for x in v]
    return v

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": int(time.time()),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "stage": _STAGE,
        }
        # Include extras added via extra={...}
        for k, v in record.__dict__.items():
            if k not in {
                "name","msg","args","levelname","levelno","pathname","filename","module",
                "exc_info","exc_text","stack_info","lineno","funcName","created","msecs",
                "relativeCreated","thread","threadName","processName","process"
            }:
                payload[k] = v
        return json.dumps(payload, separators=(",", ":"))

def _build_logger() -> logging.Logger:
    logger = logging.getLogger("app")
    if not logger.handlers:
        level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
        logger.setLevel(_LEVELS.get(level_name, logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # avoid duplicate lines in Lambda
    return logger

_logger = _build_logger()

def set_level(level: str) -> None:
    _logger.setLevel(_LEVELS.get(level.upper(), logging.INFO))
    os.environ["LOG_LEVEL"] = level

def log(level: str, msg: str, **fields):
    _logger.log(_LEVELS.get(level.upper(), logging.INFO), msg, extra=fields)

def debug(msg: str, **fields): _logger.debug(msg, extra=fields)
def info(msg: str, **fields):  _logger.info(msg,  extra=fields)
def warn(msg: str, **fields):  _logger.warning(msg, extra=fields)
def error(msg: str, **fields): _logger.error(msg, extra=fields)