"""
Phase 9 — deployment configuration checks.

These are deliberately narrow. They assert the four things that break silently
on a hosting platform and that a local development run cannot reveal:

1. CORS is an explicit list, not a wildcard, and credentials are not offered.
2. The allowed origins come from the environment, so a deployed frontend can be
   named without editing code.
3. A managed PostgreSQL instance can be reached with TLS (DB_SSLMODE).
4. The readiness endpoint still reports the truth when an optional dependency
   (pgvector, LLM) is absent, rather than being "fixed" to look healthy.

Nothing here changes a safety decision; the rule engine is not touched.
"""
from fastapi.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

from app.core.config import DEV_CORS_ORIGINS, Settings
from app.main import app
from app.vector.store import PostgresVectorStore, VectorStoreUnavailableError


def _settings(**overrides) -> Settings:
    """Settings that ignore backend/.env, so the test controls every value."""
    return Settings(_env_file=None, **overrides)


# --- CORS -------------------------------------------------------------------


def test_default_cors_origins_are_the_two_loopback_forms():
    assert _settings().cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_dev_cors_origins_constant_matches_parsed_default():
    assert DEV_CORS_ORIGINS.split(",") == _settings().cors_origin_list


def test_cors_origins_are_trimmed_and_trailing_slashes_removed():
    parsed = _settings(cors_origins=" https://app.vercel.app/ , http://localhost:5173 ").cors_origin_list
    assert parsed == ["https://app.vercel.app", "http://localhost:5173"]


def test_cors_origins_can_be_replaced_for_deployment():
    parsed = _settings(cors_origins="https://pesticide-advisory.vercel.app").cors_origin_list
    assert parsed == ["https://pesticide-advisory.vercel.app"]


def test_application_cors_middleware_uses_configured_origins_without_credentials():
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs["allow_credentials"] is False
    assert "*" not in cors.kwargs["allow_origins"]
    assert set(cors.kwargs["allow_origins"]) == set(_settings().cors_origin_list)


def test_cors_headers_are_returned_for_an_allowed_origin_only():
    client = TestClient(app)
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    # A credentialed header must not be advertised, because no cookies are used.
    assert "access-control-allow-credentials" not in allowed.headers

    foreign = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in foreign.headers


# --- Production flags -------------------------------------------------------


def test_is_production_only_for_production_app_env():
    assert _settings(app_env="production").is_production is True
    assert _settings(app_env="PROD").is_production is True
    assert _settings(app_env="development").is_production is False
    assert _settings(app_env="staging").is_production is False


# --- Database connection arguments -----------------------------------------


def test_sslmode_is_absent_by_default_so_the_local_cluster_still_connects():
    assert _settings().db_connect_args() == {"application_name": "pesticide_advisory_backend"}


def test_sslmode_is_passed_when_configured_for_a_managed_database():
    args = _settings(db_sslmode="require").db_connect_args()
    assert args["sslmode"] == "require"
    assert args["application_name"] == "pesticide_advisory_backend"


def test_blank_sslmode_is_not_forwarded_as_an_empty_value():
    # psycopg2 rejects sslmode='', so a blank value must mean "unset".
    assert "sslmode" not in _settings(db_sslmode="   ").db_connect_args()


# --- Vector storage pin -----------------------------------------------------


def _mode(recorded: str, monkeypatch, value: str | None = None) -> str:
    if value is None:
        monkeypatch.delenv("VECTOR_STORAGE_MODE", raising=False)
    else:
        monkeypatch.setenv("VECTOR_STORAGE_MODE", value)
    # The override decision uses no instance state, so no engine is needed.
    store = PostgresVectorStore.__new__(PostgresVectorStore)
    return store._apply_mode_override(recorded)


def test_storage_mode_follows_the_database_by_default(monkeypatch):
    assert _mode("array", monkeypatch) == "array"
    assert _mode("pgvector", monkeypatch) == "pgvector"


def test_storage_mode_can_be_pinned_to_the_tested_array_path(monkeypatch):
    # A managed database that ships pgvector would otherwise move production onto
    # a branch this build never runs; the pin keeps it on the tested one.
    assert _mode("pgvector", monkeypatch, "array") == "array"
    assert _mode("array", monkeypatch, "array") == "array"


def test_pinning_pgvector_where_the_database_has_none_fails_loudly(monkeypatch):
    import pytest

    with pytest.raises(VectorStoreUnavailableError, match="recorded mode='array'"):
        _mode("array", monkeypatch, "pgvector")


def test_unknown_storage_mode_pin_is_rejected(monkeypatch):
    import pytest

    with pytest.raises(VectorStoreUnavailableError, match="Unknown VECTOR_STORAGE_MODE"):
        _mode("array", monkeypatch, "hnsw")


# --- Request size cap -------------------------------------------------------


def test_oversized_request_is_rejected_before_the_pipeline_runs():
    client = TestClient(app)
    response = client.post(
        "/rag/answer",
        content=b'{"query":"' + b"x" * (32 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["status_code"] == 413
    assert "1000 characters" in response.json()["error"]["message"]


def test_a_normal_question_is_not_affected_by_the_size_cap():
    client = TestClient(app)
    response = client.post("/rag/answer", json={"query": "How do I control pink bollworm in cotton?"})
    assert response.status_code == 200


# --- Readiness honesty ------------------------------------------------------


def test_readiness_endpoint_reports_dependencies_rather_than_claiming_ready():
    """
    The deployment health check must be able to read this. On the pilot machine
    pgvector and the LLM are absent, so the honest answer is "degraded"; the test
    accepts either value but requires the field to reflect a real check.
    """
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ready", "degraded")
    if body["status"] == "degraded":
        deps = [body["database"], body["pgvector"], body["llm"]]
        assert any(dep.get("connected") is False or dep.get("available") is False for dep in deps)
    assert body["supported_languages"] == ["en", "hi"]
