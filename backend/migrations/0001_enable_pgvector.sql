-- Migration 0001: enable the pgvector extension.
--
-- Agricultural knowledge-base tables (products, crops, approved_use,
-- safety_restriction, sources, kb_chunks, etc. - see blueprint Section 9)
-- are created in migration 0002 (Phase 5), not here.
--
-- PHASE 5 CHANGE (DEC-012) — this migration no longer hard-fails.
-- It used to be a bare `CREATE EXTENSION IF NOT EXISTS vector;`, which on the
-- project's PostgreSQL 18 Windows installation aborts with
--
--     ERROR: extension "vector" is not available
--     HINT: The extension must first be installed on the system where
--           PostgreSQL is running.
--
-- because the pgvector server files (share/extension/vector.control,
-- lib/vector.dll) are not part of that installation and cannot be compiled here
-- (no C toolchain). A failing migration would block *every* later migration and
-- therefore the entire relational knowledge base, which does not actually
-- depend on vector support.
--
-- So the attempt is made and its outcome recorded; it is not assumed. Migration
-- 0003 then chooses pgvector or exact-scan storage based on what really exists.
-- The health endpoint keeps reporting the true state: it queries
-- pg_available_extensions / pg_extension directly.

DO $$
DECLARE
    v_available boolean;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')
      INTO v_available;

    IF NOT v_available THEN
        RAISE NOTICE
            'pgvector NOT available on this server: share/extension/vector.control is missing. '
            'Skipping CREATE EXTENSION; vector storage will use the exact cosine_similarity() scan. '
            'Install pgvector and re-run migrations to upgrade.';
        RETURN;
    END IF;

    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
        RAISE NOTICE 'pgvector extension enabled.';
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE
            'pgvector is available but role % may not CREATE EXTENSION (superuser required). '
            'Vector storage will use the exact cosine_similarity() scan.',
            current_user;
    END;
END $$;
