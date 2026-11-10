-- ============================================================================
-- Phase 5 (DEC-012) — PostgreSQL + pgvector schema for Module C/D.
--
-- Mirrors the validated Pydantic models in app/knowledge_base/models.py, which
-- remain the single source of truth for business rules. The database enforces
-- the anti-fabrication rules a second time, so a hand-written INSERT cannot
-- create a record the application would reject:
--   * verification_status is restricted to the two honest values; there is no
--     'APPROVED' / 'REGISTERED' value, because this project has never checked
--     any record against the live CIB&RC product registry.
--   * a safety field marked PUBLISHED must carry a value, and one marked
--     NOT_PUBLISHED_IN_SOURCE must carry an explanatory note (never silent).
--   * advisory_status (EDUCATIONAL_ONLY / ACTIONABLE_WITH_EVIDENCE) is NOT
--     stored. It is derived on read from the safety fields so it can never go
--     stale, and a stored row cannot claim to be actionable.
--
-- Deliberately contains NO pgvector dependency: the relational knowledge base
-- must import correctly even where the pgvector server extension is absent
-- (it is absent from the stock PostgreSQL 18 Windows build — see DEC-012).
-- Vector storage is isolated in 0003 so this migration always applies.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Crops
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crops (
    crop_id         TEXT PRIMARY KEY,
    crop_name       TEXT NOT NULL,
    crop_category   TEXT NOT NULL,
    is_pilot_crop   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Sources
--
-- `reliability_tier` and the presence of a fetchable URL are what back the
-- project's *source-verification* claim. Nothing in this table asserts
-- regulatory approval.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
    source_id              TEXT PRIMARY KEY,
    title                  TEXT NOT NULL,
    authority              TEXT NOT NULL,
    url                    TEXT NOT NULL,
    publication_date       TEXT,
    publication_date_note  TEXT,
    retrieved_date         TEXT NOT NULL,
    geography              TEXT NOT NULL,
    reliability_tier       TEXT NOT NULL,
    access_note            TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sources_url_is_http CHECK (url ~* '^https?://'),
    CONSTRAINT sources_reliability_tier_known CHECK (
        reliability_tier IN ('national_regulator_ipm_package', 'state_agricultural_university')
    ),
    -- A missing publication date must never be silent (Phase 3.1 / F8).
    CONSTRAINT sources_missing_date_is_explained CHECK (
        publication_date IS NOT NULL OR publication_date_note IS NOT NULL
    )
);

-- ---------------------------------------------------------------------------
-- Approved-use knowledge records
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approved_uses (
    approved_use_id             TEXT PRIMARY KEY,
    crop_id                     TEXT NOT NULL REFERENCES crops(crop_id) ON DELETE RESTRICT,
    target_pest_common_name     TEXT NOT NULL,
    target_pest_scientific_name TEXT,
    economic_threshold_level    TEXT,
    source_id                   TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    verification_status         TEXT NOT NULL,
    verification_note           TEXT NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT approved_uses_verification_status_honest CHECK (
        verification_status IN ('VERIFIED_SOURCE_RECOMMENDATION', 'UNVERIFIED_DRAFT')
    ),
    -- The honesty statement must be substantive, not a placeholder.
    CONSTRAINT approved_uses_verification_note_substantive CHECK (
        char_length(btrim(verification_note)) > 20
    )
);

COMMENT ON COLUMN approved_uses.verification_status IS
    'Source verification only: the text was transcribed from the named, fetchable source. '
    'Never regulatory approval — no record has been cross-checked against the CIB&RC registry.';

-- ---------------------------------------------------------------------------
-- Record-level safety restrictions (PHI / REI / PPE)
--
-- Kept as one row per approved_use, matching the Phase 3 structure, for
-- backward compatibility. Per-product values live on `interventions` instead.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approved_use_safety_restrictions (
    approved_use_id TEXT PRIMARY KEY REFERENCES approved_uses(approved_use_id) ON DELETE CASCADE,
    phi_status      TEXT NOT NULL,
    phi_value       TEXT,
    phi_note        TEXT,
    rei_status      TEXT NOT NULL,
    rei_value       TEXT,
    rei_note        TEXT,
    ppe_status      TEXT NOT NULL,
    ppe_value       TEXT,
    ppe_note        TEXT,
    CONSTRAINT phi_status_known CHECK (phi_status IN ('PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE')),
    CONSTRAINT rei_status_known CHECK (rei_status IN ('PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE')),
    CONSTRAINT ppe_status_known CHECK (ppe_status IN ('PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE')),
    CONSTRAINT phi_published_has_value CHECK (phi_status <> 'PUBLISHED' OR phi_value IS NOT NULL),
    CONSTRAINT rei_published_has_value CHECK (rei_status <> 'PUBLISHED' OR rei_value IS NOT NULL),
    CONSTRAINT ppe_published_has_value CHECK (ppe_status <> 'PUBLISHED' OR ppe_value IS NOT NULL),
    CONSTRAINT phi_gap_is_explained CHECK (
        phi_status <> 'NOT_PUBLISHED_IN_SOURCE' OR phi_note IS NOT NULL
    ),
    CONSTRAINT rei_gap_is_explained CHECK (
        rei_status <> 'NOT_PUBLISHED_IN_SOURCE' OR rei_note IS NOT NULL
    ),
    CONSTRAINT ppe_gap_is_explained CHECK (
        ppe_status <> 'NOT_PUBLISHED_IN_SOURCE' OR ppe_note IS NOT NULL
    )
);

-- ---------------------------------------------------------------------------
-- Interventions / products
--
-- Each row is one recommended measure. The three safety columns are NULL when
-- no per-product PHI/REI/PPE has been sourced for this specific intervention —
-- they are never copied down from the record level, because PHI/REI legally
-- attach to a product label, not to an entire pest-management record.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interventions (
    intervention_id                BIGSERIAL PRIMARY KEY,
    approved_use_id                TEXT NOT NULL REFERENCES approved_uses(approved_use_id)
                                     ON DELETE CASCADE,
    ordinal                        INTEGER NOT NULL,
    control_type                   TEXT NOT NULL,
    description                    TEXT NOT NULL,
    active_ingredient_and_formulation TEXT,
    dosage                         TEXT,
    dosage_unit_note               TEXT,
    -- Per-product safety override (NULL = no per-product data sourced).
    safety_phi_status              TEXT,
    safety_phi_value               TEXT,
    safety_phi_note                TEXT,
    safety_rei_status              TEXT,
    safety_rei_value               TEXT,
    safety_rei_note                TEXT,
    safety_ppe_status              TEXT,
    safety_ppe_value               TEXT,
    safety_ppe_note                TEXT,
    CONSTRAINT interventions_control_type_known CHECK (
        control_type IN ('chemical', 'biological', 'cultural', 'mechanical')
    ),
    CONSTRAINT interventions_ordinal_positive CHECK (ordinal > 0),
    CONSTRAINT interventions_description_present CHECK (char_length(btrim(description)) > 0),
    -- An override is all-or-nothing: either all three fields are set (a
    -- complete per-product safety profile) or none of them are.
    CONSTRAINT interventions_safety_override_complete CHECK (
        (safety_phi_status IS NULL AND safety_rei_status IS NULL AND safety_ppe_status IS NULL)
        OR (safety_phi_status IS NOT NULL AND safety_rei_status IS NOT NULL
            AND safety_ppe_status IS NOT NULL)
    ),
    CONSTRAINT interventions_safety_phi_status_known CHECK (
        safety_phi_status IS NULL OR safety_phi_status IN ('PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE')
    ),
    CONSTRAINT interventions_safety_rei_status_known CHECK (
        safety_rei_status IS NULL OR safety_rei_status IN ('PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE')
    ),
    CONSTRAINT interventions_safety_ppe_status_known CHECK (
        safety_ppe_status IS NULL OR safety_ppe_status IN ('PUBLISHED', 'NOT_PUBLISHED_IN_SOURCE')
    ),
    CONSTRAINT interventions_phi_published_has_value CHECK (
        safety_phi_status IS DISTINCT FROM 'PUBLISHED' OR safety_phi_value IS NOT NULL
    ),
    CONSTRAINT interventions_rei_published_has_value CHECK (
        safety_rei_status IS DISTINCT FROM 'PUBLISHED' OR safety_rei_value IS NOT NULL
    ),
    CONSTRAINT interventions_ppe_published_has_value CHECK (
        safety_ppe_status IS DISTINCT FROM 'PUBLISHED' OR safety_ppe_value IS NOT NULL
    ),
    CONSTRAINT interventions_phi_gap_explained CHECK (
        safety_phi_status IS DISTINCT FROM 'NOT_PUBLISHED_IN_SOURCE' OR safety_phi_note IS NOT NULL
    ),
    CONSTRAINT interventions_rei_gap_explained CHECK (
        safety_rei_status IS DISTINCT FROM 'NOT_PUBLISHED_IN_SOURCE' OR safety_rei_note IS NOT NULL
    ),
    CONSTRAINT interventions_ppe_gap_explained CHECK (
        safety_ppe_status IS DISTINCT FROM 'NOT_PUBLISHED_IN_SOURCE' OR safety_ppe_note IS NOT NULL
    ),
    CONSTRAINT interventions_unique_ordinal UNIQUE (approved_use_id, ordinal)
);

CREATE INDEX IF NOT EXISTS interventions_approved_use_idx ON interventions (approved_use_id);

-- ---------------------------------------------------------------------------
-- Provenance (Phase 3.1 audit trail, DEC-010)
--
-- A SHA-256 here proves *integrity* (the hashed bytes are the bytes quoted in
-- verbatim_excerpt). It does not prove authenticity and it does not prove
-- regulatory approval; the `verdict` column records the human judgement.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provenance_records (
    approved_use_id  TEXT PRIMARY KEY REFERENCES approved_uses(approved_use_id) ON DELETE CASCADE,
    source_id        TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    source_url       TEXT NOT NULL,
    retrieved_date   TEXT NOT NULL,
    fetch_method     TEXT NOT NULL,
    document_sha256  TEXT NOT NULL,
    document_bytes   BIGINT NOT NULL,
    verbatim_excerpt TEXT NOT NULL,
    verdict          TEXT NOT NULL,
    notes            TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT provenance_sha256_is_64_hex CHECK (document_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT provenance_bytes_positive CHECK (document_bytes > 0),
    CONSTRAINT provenance_excerpt_substantive CHECK (char_length(btrim(verbatim_excerpt)) > 20)
);

COMMENT ON COLUMN provenance_records.document_sha256 IS
    'Integrity digest of the fetched document. Proves the quoted bytes are the hashed bytes; '
    'does NOT prove authenticity and does NOT prove CIB&RC registration/approval.';

-- ---------------------------------------------------------------------------
-- advisory_status, derived (never stored)
--
-- One definition of the Phase 3.1 gate, used by the Postgres repository and
-- available to any SQL consumer. A record is ACTIONABLE_WITH_EVIDENCE only when
-- every chemical intervention has a fully PUBLISHED PHI+REI+PPE profile (taking
-- the per-intervention override when present). Otherwise EDUCATIONAL_ONLY.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW approved_use_advisory_status AS
SELECT
    au.approved_use_id,
    CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM interventions i
            WHERE i.approved_use_id = au.approved_use_id AND i.control_type = 'chemical'
        ) THEN 'EDUCATIONAL_ONLY'
        WHEN EXISTS (
            SELECT 1
            FROM interventions i
            JOIN approved_use_safety_restrictions r
              ON r.approved_use_id = au.approved_use_id
            WHERE i.approved_use_id = au.approved_use_id
              AND i.control_type = 'chemical'
              AND (
                    COALESCE(i.safety_phi_status, r.phi_status) <> 'PUBLISHED'
                 OR COALESCE(i.safety_rei_status, r.rei_status) <> 'PUBLISHED'
                 OR COALESCE(i.safety_ppe_status, r.ppe_status) <> 'PUBLISHED'
              )
        ) THEN 'EDUCATIONAL_ONLY'
        ELSE 'ACTIONABLE_WITH_EVIDENCE'
    END AS advisory_status
FROM approved_uses au;

COMMENT ON VIEW approved_use_advisory_status IS
    'Phase 3.1 / DEC-010 gate, derived so it can never go stale. Currently every '
    'pilot record is EDUCATIONAL_ONLY because no source publishes PHI/REI/PPE.';
