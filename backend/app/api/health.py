"""
Module G support — health and readiness endpoints.

GET /health        - liveness only: is the API process running.
GET /health/ready   - readiness: aggregates real DB, pgvector, and LLM provider
                      checks. Status is "ready" only if all three are actually
                      reachable - never hardcoded.
GET /health/db, /health/pgvector, /health/llm - granular checks, useful for
                      isolating which dependency is unavailable during setup.
"""
from fastapi import APIRouter

from app.advisory.llm_provider import get_llm_provider
from app.core.config import get_settings
from app.db.connection import check_database_connection, check_pgvector_extension
from app.schemas.health import DependencyStatus, LivenessResponse, LLMStatus, ReadinessResponse
from app.services.health_service import get_readiness_status

router = APIRouter()


@router.get("/health", response_model=LivenessResponse)
def health() -> LivenessResponse:
    """Liveness check: is the API process itself running."""
    return LivenessResponse(status="ok", service="pesticide-advisory-backend")


@router.get("/health/ready", response_model=ReadinessResponse)
def health_ready() -> ReadinessResponse:
    """Readiness check: real status of database, pgvector, and the configured LLM provider."""
    return get_readiness_status()


@router.get("/health/db", response_model=DependencyStatus)
def health_db() -> DependencyStatus:
    connected, message = check_database_connection()
    return DependencyStatus(connected=connected, message=message)


@router.get("/health/pgvector", response_model=DependencyStatus)
def health_pgvector() -> DependencyStatus:
    available, message = check_pgvector_extension()
    return DependencyStatus(connected=available, message=message)


@router.get("/health/llm", response_model=LLMStatus)
def health_llm() -> LLMStatus:
    provider = get_llm_provider()
    settings = get_settings()
    available, message = provider.health_check()
    return LLMStatus(provider=settings.llm_provider, available=available, message=message)
