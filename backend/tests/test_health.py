"""
Integration tests for the health/readiness endpoints (Milestone 1).

These tests verify the ENDPOINTS behave correctly and return a real,
structured response - they intentionally do NOT assert that the database or
LLM provider are available, because that depends on the local environment
(whether backend/.env has real DB credentials, whether Ollama is running).
Asserting "ready" unconditionally would be a fabricated/hardcoded pass.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_liveness_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "pesticide-advisory-backend"


def test_health_ready_returns_structured_status():
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ready", "degraded")
    for key in ("database", "pgvector", "llm", "supported_languages"):
        assert key in body
    assert "connected" in body["database"]
    assert "connected" in body["pgvector"]
    assert "available" in body["llm"]
    assert "en" in body["supported_languages"]
    assert "hi" in body["supported_languages"]


def test_health_granular_endpoints_respond():
    for path in ("/health/db", "/health/pgvector", "/health/llm"):
        resp = client.get(path)
        assert resp.status_code == 200


def test_unknown_route_returns_structured_404():
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["status_code"] == 404
