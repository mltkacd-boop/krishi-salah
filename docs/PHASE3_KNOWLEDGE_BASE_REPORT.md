# Phase 3 — Agricultural Knowledge Base: Completion Report

**Scope:** Knowledge Representation Module (C), per the approved [PROJECT_ARCHITECTURE_BLUEPRINT.md](../01_Blueprint/PROJECT_ARCHITECTURE_BLUEPRINT.md) Section 9 schema and the explicit Phase 3 instruction to implement working code (not plans/documents) in parallel with the unresolved PostgreSQL/Ollama environment gaps from Milestone 1.

**Status:** Implemented and tested. The knowledge base is **database-independent** (reads validated JSON, no PostgreSQL required) and does **not** depend on Ollama. See [DEC-009](../01_Blueprint/DECISION_LOG.md) for the architecture decision log entry.

---

## 1. What was built

A small, fully source-traceable pilot knowledge base — **9 `approved_use` records covering all 5 pilot crops, drawn from 8 authoritative Indian sources** — served through a database-independent repository layer and a read-only REST API, with the real frontend Knowledge Base screen wired to it.

### Anti-fabrication design (how Requirements #3-5 are enforced, not just stated)

- Every `approved_use` record carries a `source_id` resolving to a `Source` record with a real `url` and a `retrieved_date` — enforced by a referential-integrity check at load time (`JSONFileKnowledgeBaseRepository._validate_referential_integrity`), not just a convention.
- `verification_status` is a closed enum with exactly two values: `VERIFIED_SOURCE_RECOMMENDATION` (a direct, traceable transcription from a named source) and `UNVERIFIED_DRAFT`. **No record in the served dataset is `UNVERIFIED_DRAFT`** — the loader actively rejects any that are, rather than silently serving them.
- Every PHI, REI, and PPE field (`SafetyField`) must declare `status: PUBLISHED` (with a `value`) or `status: NOT_PUBLISHED_IN_SOURCE` (with a `note` explaining the gap). A Pydantic model-level validator (`SafetyRestrictions.model_post_init`) **raises at construction time** if either rule is violated — it is structurally impossible to leave a safety field silently blank.
- **Result of applying this honestly:** no fetched source page published a PHI, REI, or PPE value for any pest/product combination in this pilot. All 27 safety fields (9 records × 3 fields) are `NOT_PUBLISHED_IN_SOURCE`, each with an explanatory note. This is reported here exactly as found — not hidden, not filled in from general knowledge.
- Where a source itself contains an apparent inconsistency (e.g., an "SC" liquid formulation dosed in grams on one TNAU page), it is preserved verbatim with a `dosage_unit_note` flag rather than "corrected" by assumption (see `AU-RICE-YELLOW-STEM-BORER-01` and `AU-RICE-LEAF-FOLDER-01`).

### Sources used (full detail in [SOURCES_REGISTER.md](../knowledge_base/sources/SOURCES_REGISTER.md))

| Source | Authority | Reliability tier | Records |
|---|---|---|---|
| TNAU Agritech Portal (7 pages) | Tamil Nadu Agricultural University | `state_agricultural_university` | Rice (2), Maize (1), Cotton (3), Tomato (1) |
| NIPHM/DPPQS AESA-IPM Wheat package (1 PDF) | National Institute of Plant Health Management + Directorate of Plant Protection, Quarantine & Storage (CIB&RC's parent directorate), Ministry of Agriculture, GoI | `national_regulator_ipm_package` | Wheat (2) |

`ppqs.gov.in` (403 Forbidden) and several PDF compendia (oversized/binary, not extractable) were attempted and could not be used; this is documented in the register so they are not silently re-attempted later.

---

## 2. Exact files created or modified

### Backend — Knowledge Representation module (new)
- `backend/app/knowledge_base/models.py` — Pydantic schema (`Source`, `Crop`, `SafetyField`, `SafetyRestrictions`, `Intervention`, `ApprovedUse`) with the anti-fabrication validators described above.
- `backend/app/knowledge_base/repository.py` — abstract `KnowledgeBaseRepository` interface (database-independence contract, mirrors the existing `LLMProvider` pattern).
- `backend/app/knowledge_base/json_repository.py` — concrete `JSONFileKnowledgeBaseRepository` (loads/validates the JSON seed files, no DB connection) + `get_knowledge_base_repository()` factory.
- `backend/app/knowledge_base/__init__.py` — module exports (was an empty placeholder before this phase).
- `backend/app/api/knowledge_base.py` — new read-only router: `GET /knowledge-base/crops`, `/sources`, `/approved-uses` (optional `?crop_id=`), `/approved-uses/{id}`.
- `backend/app/main.py` — modified to import and register `knowledge_base.router`.

### Knowledge-base data (new)
- `knowledge_base/seed_data/crops.json` — 5 pilot crops.
- `knowledge_base/seed_data/sources.json` — 8 source records with URL, authority, dates, reliability tier.
- `knowledge_base/seed_data/approved_uses.json` — 9 pest-management records with interventions, dosages, and explicitly-labeled safety restrictions.
- `knowledge_base/sources/SOURCES_REGISTER.md` — human-readable source register, including a record of sources that were attempted and could not be used.

### Tests (new)
- `backend/tests/test_knowledge_base.py` — 24 tests covering: DB-independent loading, all 5 crops present, referential integrity, mandatory safety-field status/notes, mandatory verification notes, schema rejection of invalid/fabricated-looking data (missing safety status, dangling references, disallowed verification_status), and the live API endpoints.

### Frontend (modified/new)
- `frontend/src/types/api.ts` — modified: added `Crop`, `Source`, `SafetyField`, `SafetyRestrictions`, `Intervention`, `ApprovedUse` types matching the backend schema.
- `frontend/src/services/knowledgeBaseService.ts` — new: typed API client calls to `/knowledge-base/*`.
- `frontend/src/hooks/useKnowledgeBase.ts` — new: loads real data, no hardcoded success state (same pattern as `useBackendHealth`).
- `frontend/src/pages/KnowledgeBase.tsx` — rewritten: renders real records grouped by crop, visibly distinguishes `PUBLISHED` vs `NOT_PUBLISHED_IN_SOURCE` safety fields, links to the original source, and shows each record's verification note. Previously an empty placeholder.
- `frontend/src/pages/Dashboard.tsx` — modified: the "Knowledge base" summary tile now shows the real record/crop/source counts instead of "Not populated".

### Documentation (modified)
- `01_Blueprint/DECISION_LOG.md` — added DEC-009 recording this phase's decisions and known gaps.
- `docs/PHASE3_KNOWLEDGE_BASE_REPORT.md` — this report (new).

---

## 3. Tests executed and results

```
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

**Result: 28 passed, 0 failed** (4 pre-existing Milestone 1 health tests + 24 new Phase 3 knowledge-base tests). No database connection and no Ollama instance were required for any of these tests to pass.

Representative checks that passed:
- `test_every_pilot_crop_has_at_least_one_record` — all 5 pilot crops have ≥1 record.
- `test_every_safety_field_has_explicit_status` — all 27 safety fields across 9 records have an explicit status, and `NOT_PUBLISHED_IN_SOURCE` fields all carry a note.
- `test_safety_field_published_without_value_is_rejected`, `test_safety_field_unpublished_without_note_is_rejected`, `test_approved_use_with_disallowed_verification_status_is_rejected` — the schema's anti-fabrication guards are real (Pydantic raises `ValidationError`), not just documented intent.
- `test_repository_rejects_dangling_crop_reference`, `test_repository_rejects_dangling_source_reference` — a deliberately broken fixture (crop/source id that doesn't exist) is rejected at load time with `KnowledgeBaseLoadError`.
- `test_api_list_crops_returns_five_pilot_crops`, `test_api_get_single_approved_use_includes_safety_restrictions_and_source` — the live FastAPI `TestClient` confirms the HTTP layer serves the same validated data.

### Live (non-TestClient) HTTP smoke test

A real `uvicorn` process was started on port 8123 and queried over actual HTTP (not just FastAPI's in-process `TestClient`):

```
GET http://127.0.0.1:8123/knowledge-base/approved-uses?crop_id=cotton
→ 200 OK
→ AU-COTTON-AMERICAN-BOLLWORM-01, AU-COTTON-PINK-BOLLWORM-01, AU-COTTON-SPOTTED-SPINY-BOLLWORM-01
```

### Frontend build

```
cd frontend
npm run build
```

**Result: succeeded** (`tsc -b && vite build`, 49 modules transformed, no type errors) after adding the new Knowledge Base types, service, hook, and page.

---

## 4. Remaining blockers (unchanged from Milestone 1, not affected by this phase)

- **PostgreSQL:** `pesticide_app` role/`pesticide_advisory` database still do not exist; no superuser credentials available. Not a blocker for Phase 3 — the knowledge-base layer was explicitly built to not require it (Requirement #7). A future `PostgresKnowledgeBaseRepository` can implement the same `KnowledgeBaseRepository` interface once the DB is reachable.
- **Ollama:** still not installed/running locally. Not a blocker for Phase 3 — no part of this phase calls the LLM provider; `LLMProvider`/`OllamaProvider` from Milestone 1 are untouched.

## 5. What was explicitly NOT done in this phase (deferred, not fabricated)

- No classifier, RAG/embedding pipeline, or rule engine was built — those remain Phases 4-6 per the approved roadmap and require the crop/product vocabulary this phase now provides.
- No product-level CIB&RC registration numbers/registration dates were added, because no live CIB&RC product-registration lookup was reachable (`ppqs.gov.in` returned 403). Every record's `verification_note` states this explicitly; the schema's `verification_status` never claims "approved" or "registered".
- PHI/REI/PPE values were not filled in from general knowledge where the source didn't publish them — they are labeled `NOT_PUBLISHED_IN_SOURCE`, per Requirement #4/#5.
- Coverage is 9 records (below the 10-20 target band in the blueprint) because the team decision (DEC-005) is that verified count, not target count, is the success criterion — no records were added or padded merely to reach a number.
