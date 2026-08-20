import pytest
import hmac
import hashlib
import json
from unittest.mock import patch, MagicMock
import sys

# Mock psycopg2 avant tout import
sys.modules['psycopg2'] = MagicMock()
sys.modules['psycopg2.extras'] = MagicMock()

from fastapi.testclient import TestClient

with patch('app.database.get_connection', MagicMock()):
    from app.main import app

client = TestClient(app)

SECRET = "test_secret"

def make_signature(payload: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"

PING_PAYLOAD = json.dumps({"zen": "Keep it logically awesome."}).encode()

def test_health_returns_ok():
    with patch('app.database.get_metrics', return_value={"total_prs": 0, "analysed": 0, "oversized": 0, "bugs_detected": 0}):
        response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_webhook_ping_invalid_signature():
    response = client.post(
        "/webhook",
        content=PING_PAYLOAD,
        headers={
            "X-GitHub-Event": "ping",
            "X-Hub-Signature-256": "sha256=invalidsignature",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 401

def test_metrics_endpoint():
    with patch('app.routers.api.db_get_metrics', 
               return_value={"total_prs": 0, "analysed": 0, "oversized": 0, "bugs_detected": 0}):
        response = client.get("/api/metrics")
    assert response.status_code == 200
    assert "total_prs" in response.json()

def test_reviews_endpoint():
    with patch('app.routers.api.get_all_reviews', return_value=[]):
        response = client.get("/api/reviews")
    assert response.status_code == 200
    assert "reviews" in response.json()
