# tests/conftest.py
import os
# Ensure critical env vars exist before test modules import application code
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
# App-specific defaults so modules that read env at import time don't crash
os.environ.setdefault("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/events-staging")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("EVENTS_TABLE", "events-staging")
os.environ.setdefault("ORDERS_TABLE", "orders-staging")
os.environ.setdefault("PAYMENTS_TABLE", "payments-staging")

import pytest

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # Re-apply values per test in case a test mutates env
    monkeypatch.setenv("QUEUE_URL", os.environ["QUEUE_URL"])
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", os.environ["STRIPE_WEBHOOK_SECRET"])
    monkeypatch.setenv("EVENTS_TABLE", "events-staging")
    monkeypatch.setenv("PAYMENTS_TABLE", "payments-staging")
    monkeypatch.setenv("ORDERS_TABLE", "orders-staging")