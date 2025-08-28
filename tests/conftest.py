# tests/conftest.py
import os
# Make sure boto3 sees a region *before* test modules import handlers
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import pytest

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # App-specific vars for all tests
    monkeypatch.setenv("TABLE_NAME", "events-staging")
    monkeypatch.setenv("QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/events-staging")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")