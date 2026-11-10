"""
Database engine/session setup for Module C (Knowledge Representation).
No table definitions here — this only provides the SQLAlchemy engine and a
connectivity check used by the health-check endpoint and setup verification.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """
    Process-wide SQLAlchemy engine.

    Pool settings are deliberately small: the development laptop has 8 GB RAM
    and PostgreSQL itself needs headroom, so the app must not open a large pool.
    `pool_pre_ping` avoids serving a dead connection after the DB restarts;
    `pool_recycle` keeps connections from outliving server-side timeouts.
    `application_name` makes this app's sessions identifiable in `pg_stat_activity`,
    which matters when diagnosing the one-time role/permission setup.
    `pool_recycle` is shorter than the idle-connection timeout a managed provider
    applies, so a recycled connection is closed by us rather than mid-request.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_recycle=1800,
            connect_args=settings.db_connect_args(),
        )
    return _engine


def dispose_engine() -> None:
    """Dispose the cached engine (used by tests and by the setup/importer CLIs)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def check_database_connection() -> tuple[bool, str]:
    """
    Attempts a lightweight connection + SELECT 1.
    Returns (is_connected, message). Never raises — callers (health endpoint,
    setup verification scripts) use the returned tuple instead of catching exceptions.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connection successful."
    except Exception as exc:  # noqa: BLE001 - intentional broad catch for a health check
        return False, f"Database connection failed: {exc}"


def check_pgvector_extension() -> tuple[bool, str]:
    """
    Checks whether the pgvector extension is installed/available in the connected database.
    Returns (is_available, message).
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
            ).fetchone()
            if result is None:
                return False, "pgvector extension is NOT available on this PostgreSQL server."
            installed = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            if installed is None:
                return False, "pgvector extension is available but not yet CREATE EXTENSION'd in this database."
            return True, "pgvector extension is installed and enabled."
    except Exception as exc:  # noqa: BLE001
        return False, f"pgvector check failed: {exc}"
