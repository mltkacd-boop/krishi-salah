"""
Module C — repository selection (Phase 5, DEC-012).

Phase 3 shipped a single, database-independent JSON repository and documented a
future `PostgresKnowledgeBaseRepository` behind the same interface. Phase 5 adds
that implementation. This factory is the only place that decides which one the
application uses, mirroring `get_llm_provider()` (DEC-004).

Selection is controlled by `KB_REPOSITORY` (never by code changes):

  json      (default) version-controlled JSON files. No database required.
            This remains the default so the application, its test suite and a
            fresh clone keep working with no PostgreSQL at all — Phase 3
            Requirement #7's DB-independence is preserved, not revoked.
  postgres  PostgreSQL only. If the database is unreachable this RAISES, so a
            misconfigured deployment fails loudly instead of serving stale JSON.
  auto      PostgreSQL if it is actually reachable and imported, otherwise JSON.
            The reason for falling back is recorded and exposed by
            `get_repository_info()` (and the /health/knowledge-base endpoint), so
            a fallback is visible rather than silent.

Both implementations satisfy `KnowledgeBaseRepository`; no consumer changes.
"""
from __future__ import annotations

import os
from typing import Optional

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.knowledge_base.repository import KnowledgeBaseRepository

KB_REPOSITORY_ENV_VAR = "KB_REPOSITORY"
VALID_MODES = ("json", "postgres", "auto")

_cached_repository: Optional[KnowledgeBaseRepository] = None
_active_backend: Optional[str] = None
_fallback_reason: Optional[str] = None


class KnowledgeBaseRepositoryUnavailable(RuntimeError):
    """Raised when KB_REPOSITORY=postgres but PostgreSQL cannot serve the KB."""


def configured_mode() -> str:
    raw = os.getenv(KB_REPOSITORY_ENV_VAR, "json").strip().lower()
    if raw in ("", None):
        return "json"
    if raw in ("pg", "postgresql", "database"):
        return "postgres"
    if raw not in VALID_MODES:
        raise ValueError(
            f"Unknown {KB_REPOSITORY_ENV_VAR}='{raw}'. Supported: {', '.join(VALID_MODES)}."
        )
    return raw


def get_knowledge_base_repository() -> KnowledgeBaseRepository:
    """Return the process-wide repository for the configured backend."""
    global _cached_repository, _active_backend, _fallback_reason
    if _cached_repository is not None:
        return _cached_repository

    mode = configured_mode()
    _fallback_reason = None

    if mode in ("postgres", "auto"):
        try:
            from app.knowledge_base.postgres_repository import PostgresKnowledgeBaseRepository

            repository = PostgresKnowledgeBaseRepository()
            # Probe with a real read: constructing the object opens no connection,
            # so a reachable-looking but unimported database would otherwise only
            # fail on the first user request.
            repository.list_approved_uses()
            _cached_repository = repository
            _active_backend = "postgres"
            return _cached_repository
        except Exception as exc:  # noqa: BLE001 - mode decides whether this is fatal
            if mode == "postgres":
                raise KnowledgeBaseRepositoryUnavailable(
                    f"{KB_REPOSITORY_ENV_VAR}=postgres but the database cannot serve the "
                    f"knowledge base: {exc}"
                ) from exc
            _fallback_reason = str(exc)

    _cached_repository = JSONFileKnowledgeBaseRepository()
    _active_backend = "json"
    return _cached_repository


def get_repository_info() -> dict:
    """Describe what is actually serving the KB — for /health and diagnostics."""
    try:
        mode = configured_mode()
    except ValueError as exc:
        return {"configured": os.getenv(KB_REPOSITORY_ENV_VAR), "active": None, "error": str(exc)}
    if _cached_repository is None:
        get_knowledge_base_repository()
    return {
        "configured": mode,
        "active": _active_backend,
        "fallback_reason": _fallback_reason,
        "repository_class": type(_cached_repository).__name__ if _cached_repository else None,
    }


def reset_knowledge_base_repository_cache() -> None:
    """Drop the cached repository (tests, or after provisioning/importing)."""
    global _cached_repository, _active_backend, _fallback_reason
    _cached_repository = None
    _active_backend = None
    _fallback_reason = None
