-- ============================================================================
-- Phase 5 (DEC-012) — vector storage for Module D retrieval.
--
-- DESIGN CONSTRAINT (measured, not assumed): the pgvector *server extension* is
-- not present in the stock PostgreSQL 18 Windows installation used for this
-- project (no share/extension/vector.control, no lib/vector.dll), and it cannot
-- be compiled here because no C toolchain is installed. A migration that hard-
-- required `CREATE EXTENSION vector` therefore could never apply on the
-- development machine, which would make the whole knowledge base unimportable.
--
-- So the vector payload is stored in a plain `real[]` column, which PostgreSQL
-- has always supported, and pgvector is *opportunistically* upgraded to:
--   * when the extension is present, an HNSW index is built on the expression
--     `(embedding::vector(384))`, so similarity search uses the extension's
--     index and `<=>` operator;
--   * otherwise similarity search falls back to an exact scan using the
--     `cosine_similarity()` SQL function below.
-- Both paths return identical results (cosine similarity); only the speed
-- differs. `vector_storage_mode` records which one this database actually got,
-- so the application never has to guess and never silently claims pgvector.
--
-- The dimension (384) is fixed to match the default embedding provider. A
-- different provider dimension requires a new migration plus a re-import.
-- ============================================================================

CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id     BIGSERIAL PRIMARY KEY,
    chunk_type       TEXT NOT NULL,
    chunk_ref        TEXT NOT NULL,
    approved_use_id  TEXT REFERENCES approved_uses(approved_use_id) ON DELETE CASCADE,
    content          TEXT NOT NULL,
    -- Plain array so this table exists on every PostgreSQL build.
    embedding        real[] NOT NULL,
    embedding_dim    INTEGER NOT NULL,
    embedding_model  TEXT NOT NULL,
    content_sha256   TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT embeddings_chunk_type_known CHECK (
        chunk_type IN ('approved_use', 'intervention', 'source')
    ),
    CONSTRAINT embeddings_dim_expected CHECK (embedding_dim = 384),
    CONSTRAINT embeddings_array_length_matches CHECK (cardinality(embedding) = embedding_dim),
    CONSTRAINT embeddings_content_present CHECK (char_length(btrim(content)) > 0),
    CONSTRAINT embeddings_unique_chunk UNIQUE (chunk_type, chunk_ref, embedding_model)
);

CREATE INDEX IF NOT EXISTS embeddings_ref_idx ON embeddings (chunk_type, chunk_ref);

-- ---------------------------------------------------------------------------
-- Exact cosine similarity for the array path.
--
-- Returns NULL for mismatched or zero-length vectors rather than 0.0, so a bad
-- query vector is visibly wrong instead of looking like "no similarity".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION cosine_similarity(a real[], b real[])
RETURNS double precision
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT CASE
             WHEN cardinality(a) <> cardinality(b) THEN NULL
             WHEN s.na = 0 OR s.nb = 0 THEN NULL
             ELSE s.dot / sqrt(s.na * s.nb)
           END
    FROM (
        SELECT sum(t.x * t.y) AS dot,
               sum(t.x * t.x) AS na,
               sum(t.y * t.y) AS nb
        FROM unnest(a, b) AS t(x, y)
    ) AS s;
$$;

COMMENT ON FUNCTION cosine_similarity(real[], real[]) IS
    'Cosine similarity in [-1,1]. Exact-scan fallback used when the pgvector server extension is unavailable.';

-- ---------------------------------------------------------------------------
-- Which storage path this database actually has.
-- Single-row table: the mode is a property of the database, not of a run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vector_storage_mode (
    singleton   BOOLEAN PRIMARY KEY DEFAULT TRUE,
    mode        TEXT NOT NULL,
    detail      TEXT NOT NULL,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT vector_storage_mode_singleton CHECK (singleton),
    CONSTRAINT vector_storage_mode_known CHECK (mode IN ('pgvector', 'array'))
);

-- ---------------------------------------------------------------------------
-- Attempt the pgvector upgrade. Every step is non-fatal: a missing extension,
-- a role without CREATE EXTENSION privilege, or an old pgvector build without
-- HNSW all degrade to the exact-scan path with an explanatory `detail`.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_available boolean;
    v_installed boolean;
    v_index     text;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')
      INTO v_available;

    IF v_available THEN
        BEGIN
            CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION WHEN insufficient_privilege THEN
            v_available := false;
        END;
    END IF;

    SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
      INTO v_installed;

    IF v_installed THEN
        -- HNSW needs pgvector >= 0.5; fall back to ivfflat on older builds.
        BEGIN
            EXECUTE 'CREATE INDEX IF NOT EXISTS embeddings_hnsw_cosine_idx '
                 || 'ON embeddings USING hnsw ((embedding::vector(384)) vector_cosine_ops)';
            v_index := 'hnsw';
        EXCEPTION WHEN undefined_object OR feature_not_supported OR syntax_error THEN
            BEGIN
                EXECUTE 'CREATE INDEX IF NOT EXISTS embeddings_ivfflat_cosine_idx '
                     || 'ON embeddings USING ivfflat ((embedding::vector(384)) vector_cosine_ops) '
                     || 'WITH (lists = 100)';
                v_index := 'ivfflat';
            EXCEPTION WHEN undefined_object OR feature_not_supported OR syntax_error THEN
                v_index := 'none';
            END;
        END;

        INSERT INTO vector_storage_mode (singleton, mode, detail)
        VALUES (TRUE, 'pgvector', 'pgvector extension installed; cosine index: ' || v_index
                                   || ' on (embedding::vector(384)); search uses the <=> operator')
        ON CONFLICT (singleton) DO UPDATE
            SET mode = EXCLUDED.mode, detail = EXCLUDED.detail, decided_at = now();
    ELSE
        INSERT INTO vector_storage_mode (singleton, mode, detail)
        VALUES (
            TRUE,
            'array',
            CASE WHEN v_available
                 THEN 'pgvector files are present but this role may not CREATE EXTENSION; '
                      'using exact cosine_similarity() scan over real[]'
                 ELSE 'pgvector extension is not available on this server; '
                      'using exact cosine_similarity() scan over real[]'
            END
        )
        ON CONFLICT (singleton) DO UPDATE
            SET mode = EXCLUDED.mode, detail = EXCLUDED.detail, decided_at = now();
    END IF;
END $$;
