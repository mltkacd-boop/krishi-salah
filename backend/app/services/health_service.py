"""
Module G support — aggregates real dependency checks (DB, pgvector, LLM
provider) into a single readiness status. No field here is hardcoded to a
fixed value; every status is produced by actually calling the underlying
check function at request time.
"""
from app.advisory.llm_provider import get_llm_provider
from app.core.config import get_settings
from app.db.connection import check_database_connection, check_pgvector_extension
from app.schemas.health import DependencyStatus, LLMStatus, ReadinessResponse


def get_readiness_status() -> ReadinessResponse:
    db_connected, db_message = check_database_connection()
    pgvector_available, pgvector_message = check_pgvector_extension()

    settings = get_settings()
    provider = get_llm_provider()
    llm_available, llm_message = provider.health_check()

    overall_status = "ready" if (db_connected and pgvector_available and llm_available) else "degraded"

    return ReadinessResponse(
        status=overall_status,
        database=DependencyStatus(connected=db_connected, message=db_message),
        pgvector=DependencyStatus(connected=pgvector_available, message=pgvector_message),
        llm=LLMStatus(provider=settings.llm_provider, available=llm_available, message=llm_message),
        supported_languages=settings.supported_language_list,
    )
