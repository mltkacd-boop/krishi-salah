"""
Minimal migration runner for Module C (Phase 5 / DEC-012).

Applies .sql files from backend/migrations/ in filename order, tracking applied
versions in a `schema_migrations` table so re-running is idempotent.

Why the raw DBAPI cursor instead of SQLAlchemy `text()` / `exec_driver_sql()`:
the migrations are hand-written PostgreSQL DDL containing dollar-quoted DO
blocks, `::` casts, LIKE patterns and `%` inside RAISE NOTICE format strings.
Handing that to SQLAlchemy's statement layer causes two real, measured failures:

  * `text(...)` treats the file as a parameterised statement, so `%` reaches the
    driver as a placeholder and psycopg2 rejects the statement;
  * `exec_driver_sql(...)` mangles the same statements through its
    execution-options path (`TypeError: immutabledict is not a sequence`).

Executing the file through `cursor.execute(sql_text)` with no parameters keeps
the SQL that runs byte-identical to the SQL reviewed in the repository, and
still runs inside a single transaction per migration: a migration either
applies completely and is recorded, or rolls back untouched.

Usage (from backend/, with the venv active and backend/.env configured):
    python -m app.db.run_migrations
"""
import pathlib

from sqlalchemy import text

from app.db.connection import get_engine

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "migrations"


def _dbapi_cursor(conn):
    """Raw psycopg2 cursor for the current SQLAlchemy transaction."""
    return conn.connection.dbapi_connection.cursor()


def applied_migrations() -> list[str]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version VARCHAR(50) PRIMARY KEY, "
                "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
        )
        return [
            row[0]
            for row in conn.execute(
                text("SELECT version FROM schema_migrations ORDER BY version")
            )
        ]


def run_migrations() -> list[str]:
    """Apply every pending migration. Returns the versions applied in this run."""
    engine = get_engine()
    already_applied = set(applied_migrations())
    applied: list[str] = []

    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = sql_file.stem
        if version in already_applied:
            continue
        sql_text = sql_file.read_text(encoding="utf-8")

        with engine.begin() as conn:
            cursor = _dbapi_cursor(conn)
            try:
                cursor.execute(sql_text)
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
                )
            finally:
                cursor.close()
        applied.append(version)

    return applied


if __name__ == "__main__":
    try:
        result = run_migrations()
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint: report cleanly instead of a raw traceback
        print(f"Migration failed: could not connect or apply migrations.\nReason: {exc}")
        print("Check backend/.env DATABASE_URL and that the target role/database exist.")
        raise SystemExit(1)

    if result:
        print(f"Applied migrations: {result}")
    else:
        print("No new migrations to apply (database already up to date).")
