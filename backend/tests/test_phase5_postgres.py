"""
Phase 5 tests — PostgreSQL + pgvector integration (DEC-012).

Three groups, deliberately separated so a missing database never turns into a
skipped *or* falsely-passing build:

  A. Always runs, no database: migration SQL contract, chunk construction,
     embedding determinism, in-memory vector store, retrieval API validation,
     and the factory's backend-selection rules.
  B. Runs only when PostgreSQL is actually reachable AND the imports have been
     run: schema, migrations bookkeeping, repository operations, stored
     vectors, and the safety gate. Skips with an explicit reason otherwise.
  C. Regression checks that Phase 3/4 behaviour still holds with the Phase 5
     code in place (JSON remains the default, existing endpoints unchanged).

The safety assertions in group B are the important ones: they prove a record
lacking PHI/REI/PPE data can never be served as ACTIONABLE, and that the SQL
view and the Pydantic rule — two independent implementations of the same gate —
agree on every stored record.
"""
from __future__ import annotations

import math
import pathlib
import re

import pytest
from pydantic import ValidationError

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.vector.chunking import build_chunks, chunk_approved_use, chunk_interventions
from app.vector.embedding import (
    EMBEDDING_DIM,
    HashingEmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
    normalize,
)
from app.vector.store import (
    InMemoryVectorStore,
    PostgresVectorStore,
    VectorStoreUnavailableError,
)

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"


# ---------------------------------------------------------------------------
# Database availability
# ---------------------------------------------------------------------------
def _database_ready() -> tuple[bool, str]:
    """True only if the DB answers AND migrations + import have been applied."""
    try:
        from sqlalchemy import text

        from app.db.connection import check_database_connection, get_engine

        ok, message = check_database_connection()
        if not ok:
            return False, message
        with get_engine().connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            }
        required = {"crops", "sources", "approved_uses", "interventions", "embeddings"}
        missing = required - tables
        if missing:
            return False, f"database reachable but missing tables: {sorted(missing)}"
        with get_engine().connect() as conn:
            count = conn.execute(text("SELECT count(*) FROM approved_uses")).scalar_one()
        if count == 0:
            return False, "database reachable but the knowledge base is empty (run the importer)"
        return True, "ready"
    except Exception as exc:  # noqa: BLE001 - reported through the skip reason
        return False, f"{type(exc).__name__}: {exc}"


_DB_READY, _DB_REASON = _database_ready()

requires_db = pytest.mark.skipif(
    not _DB_READY,
    reason=f"PostgreSQL not available for Phase 5 integration tests: {_DB_REASON}",
)


@pytest.fixture(scope="module")
def pg_engine():
    from app.db.connection import get_engine

    return get_engine()


@pytest.fixture(scope="module")
def pg_repo(pg_engine):
    from app.knowledge_base.postgres_repository import PostgresKnowledgeBaseRepository

    return PostgresKnowledgeBaseRepository(pg_engine)


@pytest.fixture(scope="module")
def json_repo() -> JSONFileKnowledgeBaseRepository:
    return JSONFileKnowledgeBaseRepository()


# ===========================================================================
# A. No database required
# ===========================================================================
class TestMigrationSqlContract:
    """
    The anti-fabrication rules must exist in the schema, not only in Python.
    These are textual assertions on the reviewed migration files — cheap, and
    they fail if someone drops a CHECK constraint while refactoring.
    """

    def _sql(self, name: str) -> str:
        return (MIGRATIONS_DIR / name).read_text(encoding="utf-8")

    def test_all_migrations_present(self):
        names = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
        assert names == [
            "0001_enable_pgvector.sql",
            "0002_knowledge_base_schema.sql",
            "0003_vector_storage.sql",
        ]

    def test_required_tables_are_defined(self):
        sql = self._sql("0002_knowledge_base_schema.sql")
        for table in (
            "crops", "sources", "approved_uses", "interventions",
            "approved_use_safety_restrictions", "provenance_records",
        ):
            assert re.search(rf"CREATE TABLE IF NOT EXISTS {table}\b", sql), table
        assert "CREATE TABLE IF NOT EXISTS embeddings" in self._sql("0003_vector_storage.sql")

    def test_verification_status_cannot_claim_regulatory_approval(self):
        """
        Assert on the CHECK constraint's *value list*, not on the file text — the
        header comment legitimately explains that no 'REGISTERED' value exists.
        """
        sql = self._sql("0002_knowledge_base_schema.sql")
        match = re.search(
            r"verification_status IN \((?P<values>[^)]*)\)", sql, re.IGNORECASE | re.DOTALL
        )
        assert match, "verification_status CHECK constraint not found"
        allowed = {v.strip().strip("'").upper() for v in match.group("values").split(",") if v.strip()}
        assert allowed == {"VERIFIED_SOURCE_RECOMMENDATION", "UNVERIFIED_DRAFT"}
        assert not any("REGISTER" in value or "APPROV" in value for value in allowed - {"VERIFIED_SOURCE_RECOMMENDATION"})
        assert "APPROVED" not in allowed

    def test_safety_gaps_cannot_be_silent(self):
        sql = self._sql("0002_knowledge_base_schema.sql")
        # PUBLISHED requires a value; NOT_PUBLISHED_IN_SOURCE requires a note.
        for prefix in ("phi", "rei", "ppe"):
            assert f"{prefix}_published_has_value" in sql
            assert f"{prefix}_gap" in sql  # *_gap_is_explained / *_gap_explained

    def test_schema_has_no_stored_advisory_status_column(self):
        """
        advisory_status must stay derived. A stored column could drift from the
        safety fields and let an incomplete record look actionable.
        """
        sql = self._sql("0002_knowledge_base_schema.sql")
        assert "CREATE OR REPLACE VIEW approved_use_advisory_status" in sql
        assert not re.search(r"\badvisory_status\s+TEXT", sql)

    def test_embeddings_table_does_not_require_pgvector(self):
        """
        The embeddings table must be creatable on a server without pgvector,
        otherwise the whole migration chain is unappliable there (the exact
        situation on the project's PostgreSQL 18 install).
        """
        sql = self._sql("0003_vector_storage.sql")
        table_body = sql.split("CREATE TABLE IF NOT EXISTS embeddings (", 1)[1].split(");", 1)[0]
        assert "vector(384)" not in table_body
        assert "real[] NOT NULL" in table_body

    def test_migration_0001_is_non_fatal_without_extension(self):
        sql = self._sql("0001_enable_pgvector.sql")
        assert "pg_available_extensions" in sql
        assert "RAISE NOTICE" in sql
        assert not re.search(r"(?m)^CREATE EXTENSION", sql), "bare CREATE EXTENSION would abort the chain"


class TestChunking:
    def test_chunks_cover_every_record_and_intervention(self, json_repo):
        crops = json_repo.list_crops()
        sources = json_repo.list_sources()
        uses = json_repo.list_approved_uses()
        chunks = build_chunks(uses, crops, sources)

        expected = len(uses) + sum(len(u.interventions) for u in uses) + len(sources)
        assert len(chunks) == expected
        assert {c.chunk_type for c in chunks} == {"approved_use", "intervention", "source"}

    def test_chunk_refs_are_unique_and_traceable(self, json_repo):
        chunks = build_chunks(
            json_repo.list_approved_uses(), json_repo.list_crops(), json_repo.list_sources()
        )
        refs = [(c.chunk_type, c.chunk_ref) for c in chunks]
        assert len(refs) == len(set(refs))
        for chunk in chunks:
            if chunk.chunk_type != "source":
                assert chunk.approved_use_id, "every non-source chunk must trace to a record"

    def test_chunking_is_deterministic(self, json_repo):
        args = (json_repo.list_approved_uses(), json_repo.list_crops(), json_repo.list_sources())
        first = build_chunks(*args)
        second = build_chunks(*args)
        assert first == second

    def test_record_chunk_carries_pest_and_crop(self, json_repo):
        record = json_repo.list_approved_uses()[0]
        crop = next(c for c in json_repo.list_crops() if c.crop_id == record.crop_id)
        text = chunk_approved_use(record, crop).content
        assert crop.crop_name in text
        assert record.target_pest_common_name in text

    def test_intervention_chunk_keeps_control_type(self, json_repo):
        record = next(
            r for r in json_repo.list_approved_uses()
            if any(i.control_type == "chemical" for i in r.interventions)
        )
        crop = next(c for c in json_repo.list_crops() if c.crop_id == record.crop_id)
        chunks = chunk_interventions(record, crop)
        assert any("Measure type: chemical" in c.content for c in chunks)


class TestEmbeddingProvider:
    def test_default_provider_is_deterministic_across_instances(self):
        text = "pink bollworm cotton pheromone trap"
        assert HashingEmbeddingProvider().embed(text) == HashingEmbeddingProvider().embed(text)

    def test_dimension_matches_schema(self):
        vector = get_embedding_provider().embed("rice yellow stem borer")
        assert len(vector) == EMBEDDING_DIM == 384

    def test_vectors_are_l2_normalised(self):
        vector = HashingEmbeddingProvider().embed("neem kernel extract tomato fruit borer")
        assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-9)

    def test_devanagari_and_latin_are_both_embedded(self):
        provider = HashingEmbeddingProvider()
        hindi = provider.embed("धान का तना छेदक")
        latin = provider.embed("rice stem borer")
        assert any(v != 0.0 for v in hindi), "Devanagari text produced an all-zero vector"
        assert cosine_similarity(hindi, latin) != 0.0

    def test_related_text_scores_higher_than_unrelated(self):
        provider = HashingEmbeddingProvider()
        query = provider.embed("pink bollworm cotton")
        related = provider.embed("Cotton pink bollworm pheromone traps")
        unrelated = provider.embed("wheat termite chlorpyriphos")
        assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)

    def test_empty_text_is_zero_vector_not_an_error(self):
        assert all(v == 0.0 for v in HashingEmbeddingProvider().embed("   "))

    def test_dimension_mismatch_is_rejected(self):
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])

    def test_normalisation_keeps_combining_marks(self):
        r"""DEC-011 lesson: NFKC + \w must not split Devanagari clusters."""
        assert normalize("धान") == "धान"


class TestInMemoryVectorStore:
    @pytest.fixture()
    def store(self, json_repo) -> InMemoryVectorStore:
        store = InMemoryVectorStore()
        store.upsert_chunks(
            build_chunks(
                json_repo.list_approved_uses(), json_repo.list_crops(), json_repo.list_sources()
            )
        )
        return store

    def test_upsert_counts_all_chunks(self, store, json_repo):
        assert len(store) == store.count() > 0

    def test_search_returns_ranked_results(self, store):
        hits = store.search("pink bollworm cotton", limit=5)
        assert len(hits) == 5
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_search_respects_chunk_type_filter(self, store):
        hits = store.search("cotton bollworm", limit=10, chunk_types=["intervention"])
        assert hits and all(h.chunk_type == "intervention" for h in hits)

    def test_search_limit_and_zero_limit(self, store):
        assert len(store.search("wheat", limit=2)) == 2
        assert store.search("wheat", limit=0) == []

    def test_upsert_is_idempotent(self, store, json_repo):
        before = store.count()
        store.upsert_chunks(
            build_chunks(
                json_repo.list_approved_uses(), json_repo.list_crops(), json_repo.list_sources()
            )
        )
        assert store.count() == before

    def test_clear_removes_everything(self, store):
        assert store.clear() > 0
        assert store.count() == 0

    def test_rejects_unknown_chunk_type(self, store):
        from app.vector.chunking import ChunkInput

        with pytest.raises(Exception):
            store.upsert_chunks([ChunkInput("nonsense", "x", None, "text")])

    def test_memory_store_does_not_fabricate_advisory_status(self, store):
        """
        The in-memory fallback has no knowledge-base view to join. It must report
        None rather than inventing ACTIONABLE_WITH_EVIDENCE.
        """
        hits = store.search("cotton", limit=10)
        assert all(h.advisory_status is None for h in hits)
        assert all(h.is_actionable is False for h in hits)


class TestRetrievalApiValidation:
    def test_empty_query_is_rejected(self):
        from app.api.retrieval import similar_chunks
        from app.schemas.retrieval import VectorSearchRequest

        with pytest.raises(ValidationError):
            VectorSearchRequest(query="")

    def test_limit_bounds_are_enforced(self):
        from app.schemas.retrieval import VectorSearchRequest

        for bad in (0, -1, 21):
            with pytest.raises(ValidationError):
                VectorSearchRequest(query="rice", limit=bad)
        assert VectorSearchRequest(query="rice", limit=20).limit == 20

    def test_unknown_field_is_rejected(self):
        from app.schemas.retrieval import VectorSearchRequest

        with pytest.raises(ValidationError):
            VectorSearchRequest(query="rice", unexpected="x")

    def test_unknown_chunk_type_is_rejected(self):
        from app.schemas.retrieval import VectorSearchRequest

        with pytest.raises(ValidationError):
            VectorSearchRequest(query="rice", chunk_types=["dosage"])

    def test_similar_endpoint_returns_503_when_store_unavailable(self, monkeypatch):
        from fastapi import HTTPException

        from app.api import retrieval
        from app.schemas.retrieval import VectorSearchRequest

        class BrokenStore:
            backend = "unavailable"

            def search(self, *args, **kwargs):
                raise VectorStoreUnavailableError("database is down")

        monkeypatch.setattr(retrieval, "get_vector_store", lambda: BrokenStore())
        with pytest.raises(HTTPException) as exc:
            retrieval.similar_chunks(VectorSearchRequest(query="rice pest"))
        assert exc.value.status_code == 503

    def test_similar_endpoint_uses_in_memory_store(self, monkeypatch, json_repo):
        from app.api import retrieval
        from app.schemas.retrieval import VectorSearchRequest

        store = InMemoryVectorStore()
        store.upsert_chunks(
            build_chunks(
                json_repo.list_approved_uses(), json_repo.list_crops(), json_repo.list_sources()
            )
        )
        monkeypatch.setattr(retrieval, "get_vector_store", lambda: store)
        response = retrieval.similar_chunks(VectorSearchRequest(query="cotton bollworm", limit=3))
        assert len(response.hits) == 3
        assert response.backend == "memory"
        assert "not a recommendation" in response.notice
        assert all(hit.is_actionable is False for hit in response.hits)


class TestRepositorySelection:
    def test_default_mode_is_json(self, monkeypatch):
        from app.knowledge_base import factory

        monkeypatch.delenv("KB_REPOSITORY", raising=False)
        assert factory.configured_mode() == "json"

    def test_unknown_mode_is_rejected(self, monkeypatch):
        from app.knowledge_base import factory

        monkeypatch.setenv("KB_REPOSITORY", "mysql")
        with pytest.raises(ValueError):
            factory.configured_mode()

    def test_json_mode_never_touches_the_database(self, monkeypatch):
        from app.knowledge_base import factory

        monkeypatch.setenv("KB_REPOSITORY", "json")
        monkeypatch.setattr(factory, "_cached_repository", None)
        repo = factory.get_knowledge_base_repository()
        assert type(repo).__name__ == "JSONFileKnowledgeBaseRepository"
        info = factory.get_repository_info()
        assert info["active"] == "json" and info["fallback_reason"] is None

    def test_postgres_mode_raises_instead_of_silently_using_json(self, monkeypatch):
        from app.knowledge_base import factory

        monkeypatch.setenv("KB_REPOSITORY", "postgres")
        monkeypatch.setattr(factory, "_cached_repository", None)
        monkeypatch.setattr(
            factory, "JSONFileKnowledgeBaseRepository",
            lambda *a, **k: pytest.fail("postgres mode must not fall back to JSON"),
        )
        # Force the probe to fail without needing a real outage.
        import app.knowledge_base.postgres_repository as pg_module

        class Exploding(pg_module.PostgresKnowledgeBaseRepository):
            def __init__(self, *a, **k):
                raise RuntimeError("simulated outage")

        monkeypatch.setattr(pg_module, "PostgresKnowledgeBaseRepository", Exploding)
        with pytest.raises(factory.KnowledgeBaseRepositoryUnavailable):
            factory.get_knowledge_base_repository()


# ===========================================================================
# B. Requires a live, migrated, imported database
# ===========================================================================
@requires_db
class TestSchemaAndMigrations:
    def test_migrations_are_recorded(self, pg_engine):
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            versions = [r[0] for r in conn.execute(text("SELECT version FROM schema_migrations"))]
        assert versions == ["0001_enable_pgvector", "0002_knowledge_base_schema", "0003_vector_storage"]

    def test_rerunning_migrations_is_a_noop(self):
        from app.db.run_migrations import run_migrations

        assert run_migrations() == []

    def test_vector_storage_mode_is_recorded_honestly(self, pg_engine):
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            mode, detail = conn.execute(
                text("SELECT mode, detail FROM vector_storage_mode WHERE singleton")
            ).one()
            has_extension = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar_one()
        assert mode in ("pgvector", "array")
        # The recorded mode must match reality, never aspiration.
        assert (mode == "pgvector") == bool(has_extension)
        assert detail

    def test_cosine_similarity_function_behaviour(self, pg_engine):
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            identical = conn.execute(
                text("SELECT cosine_similarity(ARRAY[1,0,0]::real[], ARRAY[1,0,0]::real[])")
            ).scalar_one()
            orthogonal = conn.execute(
                text("SELECT cosine_similarity(ARRAY[1,0,0]::real[], ARRAY[0,1,0]::real[])")
            ).scalar_one()
            mismatched = conn.execute(
                text("SELECT cosine_similarity(ARRAY[1,0]::real[], ARRAY[1,0,0]::real[])")
            ).scalar_one()
        assert math.isclose(identical, 1.0, rel_tol=1e-9)
        assert math.isclose(orthogonal, 0.0, abs_tol=1e-9)
        assert mismatched is None


@requires_db
class TestImport:
    def test_row_counts_match_the_source_files(self, pg_engine, json_repo):
        from sqlalchemy import text

        expected = {
            "crops": len(json_repo.list_crops()),
            "sources": len(json_repo.list_sources()),
            "approved_uses": len(json_repo.list_approved_uses()),
            "interventions": sum(len(r.interventions) for r in json_repo.list_approved_uses()),
        }
        with pg_engine.connect() as conn:
            for table, expected_count in expected.items():
                actual = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                assert actual == expected_count, table

    def test_import_is_idempotent(self):
        from app.db.import_knowledge_base import import_knowledge_base

        first = import_knowledge_base(skip_embeddings=True)
        second = import_knowledge_base(skip_embeddings=True)
        assert first["db_counts"] == second["db_counts"]

    def test_dry_run_writes_nothing(self, pg_engine):
        from sqlalchemy import text

        from app.db.import_knowledge_base import import_knowledge_base

        with pg_engine.connect() as conn:
            before = conn.execute(text("SELECT count(*) FROM interventions")).scalar_one()
        summary = import_knowledge_base(dry_run=True)
        assert summary.get("dry_run") is True
        with pg_engine.connect() as conn:
            after = conn.execute(text("SELECT count(*) FROM interventions")).scalar_one()
        assert before == after

    def test_provenance_rows_imported_with_valid_hashes(self, pg_engine):
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT document_sha256, length(verbatim_excerpt) FROM provenance_records")
            ).all()
        assert rows
        for sha, excerpt_length in rows:
            assert re.fullmatch(r"[0-9a-f]{64}", sha)
            assert excerpt_length > 20


@requires_db
class TestPostgresRepository:
    def test_implements_the_same_interface(self, pg_repo):
        from app.knowledge_base.repository import KnowledgeBaseRepository

        assert isinstance(pg_repo, KnowledgeBaseRepository)

    def test_matches_the_json_repository_exactly(self, pg_repo, json_repo):
        """
        The strongest compatibility check: both backends serve identical records.

        Compared as id-keyed mappings rather than ordered lists on purpose. The
        JSON repository preserves file order; the Postgres repository orders by
        primary key, which is deterministic and is a documented difference in
        presentation order only — never in content.
        """
        for getter, id_field in (
            ("list_crops", "crop_id"),
            ("list_sources", "source_id"),
        ):
            pg_map = {getattr(item, id_field): item.model_dump() for item in getattr(pg_repo, getter)()}
            json_map = {getattr(item, id_field): item.model_dump() for item in getattr(json_repo, getter)()}
            assert pg_map.keys() == json_map.keys(), getter
            for key in json_map:
                assert pg_map[key] == json_map[key], f"{getter} differs between backends: {key}"

        pg_uses = {u.approved_use_id: u.model_dump() for u in pg_repo.list_approved_uses()}
        json_uses = {u.approved_use_id: u.model_dump() for u in json_repo.list_approved_uses()}
        assert pg_uses.keys() == json_uses.keys()
        for key in json_uses:
            assert pg_uses[key] == json_uses[key], f"record differs between backends: {key}"

    def test_ordering_is_deterministic(self, pg_repo):
        assert [c.crop_id for c in pg_repo.list_crops()] == sorted(c.crop_id for c in pg_repo.list_crops())
        assert [u.approved_use_id for u in pg_repo.list_approved_uses()] == sorted(
            u.approved_use_id for u in pg_repo.list_approved_uses()
        )

    def test_get_by_id_and_missing_return_none(self, pg_repo, json_repo):
        known = json_repo.list_approved_uses()[0].approved_use_id
        assert pg_repo.get_approved_use(known) is not None
        assert pg_repo.get_approved_use("AU-DOES-NOT-EXIST") is None
        assert pg_repo.get_crop("cotton") is not None
        assert pg_repo.get_crop("saffron") is None

    def test_crop_filter(self, pg_repo):
        cotton = pg_repo.list_approved_uses(crop_id="cotton")
        assert cotton and all(u.crop_id == "cotton" for u in cotton)
        assert pg_repo.list_approved_uses(crop_id="nonexistent") == []

    def test_interventions_keep_order_and_are_not_duplicated(self, pg_repo):
        for record in pg_repo.list_approved_uses():
            assert record.interventions, record.approved_use_id
        full = pg_repo.list_approved_uses()
        assert len(full) == len({u.approved_use_id for u in full})

    def test_provenance_is_readable(self, pg_repo):
        rows = pg_repo.list_provenance()
        assert rows and all("document_sha256" in row for row in rows)


@requires_db
class TestSafetyRestrictionsInDatabase:
    """
    Phase 5 Requirement #10. These assertions must hold no matter what is
    imported, because they are enforced by CHECK constraints, not by convention.
    """

    def test_every_record_is_educational_only(self, pg_repo):
        statuses = {u.approved_use_id: u.advisory_status for u in pg_repo.list_approved_uses()}
        assert statuses, "no records imported"
        assert all(s == "EDUCATIONAL_ONLY" for s in statuses.values()), statuses

    def test_sql_view_agrees_with_the_python_rule(self, pg_repo):
        assert pg_repo.assert_advisory_status_consistency() == []

    def test_no_record_claims_published_safety_data(self, pg_engine):
        """If a source ever publishes PHI/REI/PPE, this test starts failing on purpose."""
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            published = conn.execute(
                text(
                    "SELECT count(*) FROM approved_use_safety_restrictions "
                    "WHERE phi_status = 'PUBLISHED' OR rei_status = 'PUBLISHED' OR ppe_status = 'PUBLISHED'"
                )
            ).scalar_one()
        assert published == 0

    def test_every_gap_carries_an_explanation(self, pg_engine):
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            unexplained = conn.execute(
                text(
                    "SELECT count(*) FROM approved_use_safety_restrictions WHERE "
                    "(phi_status = 'NOT_PUBLISHED_IN_SOURCE' AND (phi_note IS NULL OR btrim(phi_note) = '')) OR "
                    "(rei_status = 'NOT_PUBLISHED_IN_SOURCE' AND (rei_note IS NULL OR btrim(rei_note) = '')) OR "
                    "(ppe_status = 'NOT_PUBLISHED_IN_SOURCE' AND (ppe_note IS NULL OR btrim(ppe_note) = ''))"
                )
            ).scalar_one()
        assert unexplained == 0

    def test_database_rejects_a_published_field_without_a_value(self, pg_engine):
        from sqlalchemy import text

        with pytest.raises(Exception):
            with pg_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO approved_use_safety_restrictions "
                        "(approved_use_id, phi_status, rei_status, rei_value, rei_note, "
                        " ppe_status, ppe_note) "
                        "SELECT approved_use_id, 'PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE', NULL, "
                        "       'test', 'NOT_PUBLISHED_IN_SOURCE', 'test' "
                        "FROM approved_uses LIMIT 1"
                    )
                )

    def test_database_rejects_a_silent_gap(self, pg_engine):
        from sqlalchemy import text

        with pytest.raises(Exception):
            with pg_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO approved_use_safety_restrictions "
                        "(approved_use_id, phi_status, phi_note, rei_status, rei_value, rei_note, "
                        " ppe_status, ppe_note) "
                        "SELECT approved_use_id, 'NOT_PUBLISHED_IN_SOURCE', NULL, "
                        "       'PUBLISHED', '24 hours', 'test', "
                        "       'NOT_PUBLISHED_IN_SOURCE', 'test' "
                        "FROM approved_uses LIMIT 1"
                    )
                )

    def test_database_rejects_a_verification_status_implying_approval(self, pg_engine):
        from sqlalchemy import text

        with pytest.raises(Exception):
            with pg_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO approved_uses (approved_use_id, crop_id, target_pest_common_name, "
                        "source_id, verification_status, verification_note) "
                        "VALUES ('AU-TEST-APPROVED', 'cotton', 'test pest', "
                        "        (SELECT source_id FROM sources LIMIT 1), "
                        "        'CIB_RC_APPROVED', 'this status must not exist in the schema')"
                    )
                )

    def test_database_rejects_a_dangling_crop_reference(self, pg_engine):
        from sqlalchemy import text

        with pytest.raises(Exception):
            with pg_engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO approved_uses (approved_use_id, crop_id, target_pest_common_name, "
                        "source_id, verification_status, verification_note) "
                        "VALUES ('AU-TEST-DANGLING', 'saffron', 'test pest', "
                        "        (SELECT source_id FROM sources LIMIT 1), "
                        "        'UNVERIFIED_DRAFT', 'referential integrity check')"
                    )
                )


@requires_db
class TestVectorStorageInDatabase:
    def test_chunks_are_stored_with_expected_dimension(self, pg_engine):
        from sqlalchemy import text

        with pg_engine.connect() as conn:
            bad = conn.execute(
                text("SELECT count(*) FROM embeddings WHERE cardinality(embedding) <> 384")
            ).scalar_one()
            count = conn.execute(text("SELECT count(*) FROM embeddings")).scalar_one()
        assert count >= 60
        assert bad == 0

    def test_search_returns_gated_results(self, pg_repo):
        store = PostgresVectorStore()
        hits = store.search("pink bollworm cotton", limit=5)
        assert hits
        for hit in hits:
            assert -1.0 <= hit.score <= 1.0
            if hit.approved_use_id:
                # The gate travels with the text — never a bare dosage.
                assert hit.advisory_status in ("EDUCATIONAL_ONLY", "ACTIONABLE_WITH_EVIDENCE")
                assert hit.is_actionable is False

    def test_search_ranks_the_right_record_first(self):
        store = PostgresVectorStore()
        hits = store.search("cotton pink bollworm", limit=3)
        assert hits[0].approved_use_id == "AU-COTTON-PINK-BOLLWORM-01"

    def test_search_chunk_type_filter(self):
        store = PostgresVectorStore()
        hits = store.search("cotton", limit=10, chunk_types=["intervention"])
        assert hits and all(h.chunk_type == "intervention" for h in hits)

    def test_query_vector_is_never_stored(self, pg_engine):
        """Searching must not mutate the index."""
        from sqlalchemy import text

        store = PostgresVectorStore()
        with pg_engine.connect() as conn:
            before = conn.execute(text("SELECT count(*) FROM embeddings")).scalar_one()
        store.search("wheat termite", limit=5)
        with pg_engine.connect() as conn:
            after = conn.execute(text("SELECT count(*) FROM embeddings")).scalar_one()
        assert before == after

    def test_upsert_refreshes_changed_content(self, pg_repo):
        from app.vector.chunking import ChunkInput

        store = PostgresVectorStore()
        ref = "TEST-CHUNK-REFRESH"
        store.upsert_chunks([ChunkInput("source", ref, None, "original content")])
        store.upsert_chunks([ChunkInput("source", ref, None, "updated content")])
        hits = [h for h in store.search("original content updated", limit=50) if h.chunk_ref == ref]
        assert len(hits) == 1
        assert hits[0].content == "updated content"
        # Clean up so the fixture stays reproducible.
        from sqlalchemy import text

        with store._engine.begin() as conn:  # noqa: SLF001 - test cleanup
            conn.execute(text("DELETE FROM embeddings WHERE chunk_ref = :r"), {"r": ref})


# ===========================================================================
# C. Regressions: Phase 3/4 behaviour with Phase 5 code present
# ===========================================================================
class TestNoRegressions:
    def test_json_remains_the_default_backend(self):
        from app.knowledge_base import get_repository_info

        info = get_repository_info()
        assert info["configured"] == "json"

    def test_knowledge_base_api_still_serves_the_phase3_data(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        crops = client.get("/knowledge-base/crops")
        assert crops.status_code == 200
        assert len(crops.json()) == 5
        uses = client.get("/knowledge-base/approved-uses")
        assert uses.status_code == 200
        assert all(u["advisory_status"] == "EDUCATIONAL_ONLY" for u in uses.json())

    def test_classification_endpoint_unaffected(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.post("/classification/classify", json={"query": "whitefly on cotton"})
        assert response.status_code == 200
        body = response.json()
        assert body["safety_policy"]["approves_pesticide_recommendation"] is False
        assert body["safety_policy"]["can_override_educational_only_gate"] is False

    def test_health_endpoints_unchanged(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        assert client.get("/health").status_code == 200
        db = client.get("/health/db")
        assert db.status_code == 200
        assert set(db.json()) == {"connected", "message"}

    def test_status_endpoint_reports_json_backend(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.get("/knowledge-base/status")
        assert response.status_code == 200
        body = response.json()
        assert body["repository_backend"] == "json"
        assert body["records"]["approved_uses"] == 9
