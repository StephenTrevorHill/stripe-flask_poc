# tests/conftest.py

import pytest

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # Keep values aligned with our stubbed expectations & sample stack
    monkeypatch.setenv("TABLE_NAME", "events-staging")
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/events-staging")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")