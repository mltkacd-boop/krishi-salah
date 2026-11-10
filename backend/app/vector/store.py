"""
Module D support — vector storage and similarity search (Phase 5, DEC-012).

Two interchangeable implementations behind one interface:

  PostgresVectorStore  real persistence; uses pgvector's `<=>` operator and an
                       HNSW/ivfflat index when the extension is installed, and
                       the exact `cosine_similarity()` scan over `real[]`
                       otherwise. Which path is in use is read from the
                       `vector_storage_mode` row written by migration 0003 —
                       the application never guesses and never claims pgvector
                       when it is not there.
  InMemoryVectorStore  pure-Python implementation used by tests and available as
                       an explicit fallback; no database required.

Every search result carries `advisory_status`, joined live from the
`approved_use_advisory_status` view. That is deliberate: retrieval must never
return a dosage without the safety gate travelling with it (Phase 3.1 /
DEC-010; Phase 5 Requirement #10).
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from app.vector.chunking import ChunkInput
from app.vector.embedding import EmbeddingProvider, cosine_similarity, get_embedding_provider

VALID_CHUNK_TYPES = ("approved_use", "intervention", "source")


class VectorStoreError(RuntimeError):
    """Base class for vector-store failures."""


class VectorStoreUnavailableError(VectorStoreError):
    """Raised when PostgreSQL cannot serve the vector store (table missing, DB down)."""


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_type: str
    chunk_ref: str
    approved_use_id: Optional[str]
    content: str
    score: float
    advisory_status: Optional[str]
    embedding_model: str

    @property
    def is_actionable(self) -> bool:
        """Only an explicit ACTIONABLE_WITH_EVIDENCE record may be rendered as a dose."""
        return self.advisory_status == "ACTIONABLE_WITH_EVIDENCE"


def content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class VectorStore(ABC):
    """Minimal interface: index chunks, search them, report what is indexed."""

    @abstractmethod
    def upsert_chunks(self, chunks: Iterable[ChunkInput]) -> int:
        """Insert or update chunks for this store's embedding model. Returns row count."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        chunk_types: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> int:
        """Delete every chunk for this store's embedding model. Returns rows deleted."""

    @property
    @abstractmethod
    def backend(self) -> str:
        """'pgvector' | 'array' | 'memory' — what actually ran, for reporting."""

    def __len__(self) -> int:
        return self.count()


class InMemoryVectorStore(VectorStore):
    """Exact cosine search in Python. Deterministic; used by tests and as a fallback."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider or get_embedding_provider()
        self._rows: dict[tuple[str, str], dict] = {}

    @property
    def backend(self) -> str:
        return "memory"

    def upsert_chunks(self, chunks: Iterable[ChunkInput]) -> int:
        count = 0
        for chunk in chunks:
            if chunk.chunk_type not in VALID_CHUNK_TYPES:
                raise VectorStoreError(f"invalid chunk_type: {chunk.chunk_type}")
            self._rows[(chunk.chunk_type, chunk.chunk_ref)] = {
                "approved_use_id": chunk.approved_use_id,
                "content": chunk.content,
                "vector": self._provider.embed(chunk.content),
                "digest": content_digest(chunk.content),
            }
            count += 1
        return count

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        chunk_types: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        if limit <= 0:
            return []
        query_vector = self._provider.embed(query)
        allowed = set(chunk_types) if chunk_types else None
        scored: list[RetrievedChunk] = []
        for (chunk_type, chunk_ref), row in self._rows.items():
            if allowed and chunk_type not in allowed:
                continue
            scored.append(RetrievedChunk(
                chunk_type=chunk_type,
                chunk_ref=chunk_ref,
                approved_use_id=row["approved_use_id"],
                content=row["content"],
                score=cosine_similarity(query_vector, row["vector"]),
                # The in-memory store has no knowledge-base view to join; it is a
                # retrieval-only fallback and therefore reports no status rather
                # than fabricating one.
                advisory_status=None,
                embedding_model=self._provider.model_id,
            ))
        scored.sort(key=lambda c: (-c.score, c.chunk_type, c.chunk_ref))
        return scored[:limit]

    def count(self) -> int:
        return len(self._rows)

    def clear(self) -> int:
        removed = len(self._rows)
        self._rows.clear()
        return removed

    def set_advisory_status(self, approved_use_id: str, status: str) -> None:
        """
        Test helper: attaches a status so gating logic can be exercised without
        a database. Production status always comes from the SQL view.
        """
        for row in self._rows.values():
            if row["approved_use_id"] == approved_use_id:
                row["advisory_status"] = status

    def status_for(self, approved_use_id: str) -> Optional[str]:
        for row in self._rows.values():
            if row["approved_use_id"] == approved_use_id:
                return row.get("advisory_status")
        return None


class PostgresVectorStore(VectorStore):
    """Durable vector store backed by the `embeddings` table (migration 0003)."""

    def __init__(self, engine=None, provider: EmbeddingProvider | None = None) -> None:
        if engine is None:
            from app.db.connection import get_engine  # local import keeps tests light
            engine = get_engine()
        self._engine = engine
        self._provider = provider or get_embedding_provider()
        self._mode: Optional[str] = None

    # --- introspection ----------------------------------------------------
    def _storage_mode(self) -> str:
        if self._mode is None:
            from sqlalchemy import text

            try:
                with self._engine.connect() as conn:
                    row = conn.execute(
                        text("SELECT mode FROM vector_storage_mode WHERE singleton")
                    ).fetchone()
            except Exception as exc:  # noqa: BLE001 - surfaced as a typed error
                raise VectorStoreUnavailableError(
                    f"vector store unavailable: {exc}. "
                    "Run the migrations (python -m app.db.run_migrations) first."
                ) from exc
            if row is None:
                raise VectorStoreUnavailableError(
                    "vector_storage_mode has no row — migration 0003 did not complete."
                )
            recorded = row[0]
            self._mode = self._apply_mode_override(recorded)
        return self._mode

    def _apply_mode_override(self, recorded: str) -> str:
        """
        Optional pin, from VECTOR_STORAGE_MODE (auto | array | pgvector).

        Migration 0003 records what the *database* can do. That is not the same
        as what this build has been tested against: the array path is the one
        covered by the Phase 5/6 test suite, and a managed provider that ships
        pgvector (Neon, Render) would otherwise switch production onto the
        untested branch by itself, silently, on first deploy.

        `array` therefore forces the exact-scan path, which is always available
        because the `real[]` column exists on every PostgreSQL build. Forcing
        `pgvector` where the database has no extension raises instead of quietly
        running the array path, so a mistaken pin is visible rather than assumed.
        """
        import os

        choice = os.getenv("VECTOR_STORAGE_MODE", "auto").strip().lower()
        if choice in ("", "auto"):
            return recorded
        if choice == "array":
            return "array"
        if choice == "pgvector":
            if recorded != "pgvector":
                raise VectorStoreUnavailableError(
                    "VECTOR_STORAGE_MODE=pgvector but this database recorded "
                    f"mode={recorded!r}. Create the extension and re-run migration 0003, "
                    "or use VECTOR_STORAGE_MODE=auto."
                )
            return "pgvector"
        raise VectorStoreUnavailableError(
            f"Unknown VECTOR_STORAGE_MODE={choice!r}. Supported: auto, array, pgvector."
        )

    @property
    def backend(self) -> str:
        try:
            return self._storage_mode()
        except VectorStoreUnavailableError:
            return "unavailable"

    def storage_detail(self) -> str:
        from sqlalchemy import text

        try:
            with self._engine.connect() as conn:
                row = conn.execute(text("SELECT detail FROM vector_storage_mode WHERE singleton")).fetchone()
            return row[0] if row else "unknown"
        except Exception as exc:  # noqa: BLE001
            return f"unavailable: {exc}"

    # --- writes -----------------------------------------------------------
    def upsert_chunks(self, chunks: Iterable[ChunkInput]) -> int:
        from sqlalchemy import text

        rows = []
        for chunk in chunks:
            if chunk.chunk_type not in VALID_CHUNK_TYPES:
                raise VectorStoreError(f"invalid chunk_type: {chunk.chunk_type}")
            vector = self._provider.embed(chunk.content)
            rows.append({
                "chunk_type": chunk.chunk_type,
                "chunk_ref": chunk.chunk_ref,
                "approved_use_id": chunk.approved_use_id,
                "content": chunk.content,
                "embedding": vector,
                "dim": len(vector),
                "model": self._provider.model_id,
                "digest": content_digest(chunk.content),
            })
        if not rows:
            return 0

        stmt = text(
            """
            INSERT INTO embeddings
                (chunk_type, chunk_ref, approved_use_id, content,
                 embedding, embedding_dim, embedding_model, content_sha256)
            VALUES
                (:chunk_type, :chunk_ref, :approved_use_id, :content,
                 (:embedding)::real[], :dim, :model, :digest)
            ON CONFLICT (chunk_type, chunk_ref, embedding_model) DO UPDATE
               SET content         = EXCLUDED.content,
                   approved_use_id = EXCLUDED.approved_use_id,
                   embedding       = EXCLUDED.embedding,
                   embedding_dim   = EXCLUDED.embedding_dim,
                   content_sha256  = EXCLUDED.content_sha256
            """
        )
        with self._engine.begin() as conn:
            conn.execute(stmt, rows)
        return len(rows)

    def clear(self) -> int:
        from sqlalchemy import text

        with self._engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM embeddings WHERE embedding_model = :m"),
                {"m": self._provider.model_id},
            )
            return result.rowcount or 0

    def count(self) -> int:
        from sqlalchemy import text

        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT count(*) FROM embeddings WHERE embedding_model = :m"),
                {"m": self._provider.model_id},
            ).fetchone()
        return int(row[0]) if row else 0

    # --- reads ------------------------------------------------------------
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        chunk_types: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        from sqlalchemy import text

        if limit <= 0:
            return []
        mode = self._storage_mode()
        query_vector = self._provider.embed(query)
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in query_vector) + "]"
        type_filter = list(chunk_types) if chunk_types else None

        base_select = """
            SELECT e.chunk_type, e.chunk_ref, e.approved_use_id, e.content,
                   {score} AS score, v.advisory_status, e.embedding_model
            FROM embeddings e
            LEFT JOIN approved_use_advisory_status v
                   ON v.approved_use_id = e.approved_use_id
            WHERE e.embedding_model = :model
              {type_clause}
              AND {not_null}
            ORDER BY {order}
            LIMIT :limit
        """

        if mode == "pgvector":
            # `<=>` is cosine distance; similarity = 1 - distance.
            score_expr = "1 - (e.embedding::vector(384) <=> (:qv)::vector)"
            order = "e.embedding::vector(384) <=> (:qv)::vector"
            not_null = "1 = 1"
            params: dict = {"model": self._provider.model_id, "qv": vector_literal, "limit": limit}
        else:
            score_expr = "cosine_similarity(e.embedding, (:qv)::real[])"
            order = "cosine_similarity(e.embedding, (:qv)::real[]) DESC"
            # A malformed/mismatched vector yields NULL rather than 0.0, so it
            # must be excluded explicitly instead of ranking as "no similarity".
            not_null = "cosine_similarity(e.embedding, (:qv)::real[]) IS NOT NULL"
            params = {"model": self._provider.model_id, "qv": query_vector, "limit": limit}

        type_clause = ""
        if type_filter:
            type_clause = "AND e.chunk_type = ANY(:types)"
            params["types"] = type_filter

        stmt = text(base_select.format(score=score_expr, order=order,
                                       type_clause=type_clause, not_null=not_null))
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(stmt, params).fetchall()
        except Exception as exc:  # noqa: BLE001 - typed error for the API layer
            raise VectorStoreUnavailableError(f"vector search failed: {exc}") from exc

        return [
            RetrievedChunk(
                chunk_type=row[0],
                chunk_ref=row[1],
                approved_use_id=row[2],
                content=row[3],
                score=float(row[4]) if row[4] is not None else float("nan"),
                advisory_status=row[5],
                embedding_model=row[6],
            )
            for row in rows
        ]


class RequireAdvisoryStatusMixin:
    """Convenience: drop results that cannot be safety-gated (no record status)."""

    @staticmethod
    def gated(results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return [r for r in results if r.approved_use_id is None or r.advisory_status is not None]


_memory_singleton: InMemoryVectorStore | None = None


def get_vector_store(backend: str | None = None) -> VectorStore:
    """
    Factory. `backend` may be 'postgres', 'memory', or None (read VECTOR_STORE,
    default 'postgres'). 'memory' is explicit so a database outage is never
    silently masked by an empty in-process index.
    """
    global _memory_singleton
    import os

    choice = (backend or os.getenv("VECTOR_STORE", "postgres")).strip().lower()
    if choice in ("memory", "in-memory", "inmemory"):
        if _memory_singleton is None:
            _memory_singleton = InMemoryVectorStore()
        return _memory_singleton
    if choice in ("postgres", "pg", "database", ""):
        return PostgresVectorStore()
    raise ValueError(f"Unknown VECTOR_STORE '{choice}'. Supported: 'postgres' (default), 'memory'.")


def reset_vector_store_cache() -> None:
    global _memory_singleton
    _memory_singleton = None
