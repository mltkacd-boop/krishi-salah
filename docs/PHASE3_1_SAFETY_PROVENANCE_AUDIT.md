# Phase 3.1 — Safety and Provenance Audit Report

**Status:** Complete. See [DEC-010](../01_Blueprint/DECISION_LOG.md#dec-010--phase-31-safety-and-provenance-audit-gating-per-product-safety-schema-hardening) for the approved decisions this report implements.

**Scope:** Re-verify all 9 pilot `approved_use` records against all 8 sources (including the 3 not yet re-verified in Phase 3), create a durable provenance manifest, close known schema gaps, add per-intervention safety-restriction capacity, correct misleading wording, and gate actionable-vs-educational use of incomplete-safety records — without blocking Phase 4 and without inventing any dosage/approval/PHI/REI/PPE value.

---

## 1. Per-record verdict table

Source: [`knowledge_base/seed_data/provenance_manifest.json`](../knowledge_base/seed_data/provenance_manifest.json) (machine-readable; this table is a human summary of it). All fetches performed 2026-11-03.

| approved_use_id | Source | Previously re-verified in Phase 3? | Verdict | Notes |
|---|---|---|---|---|
| AU-COTTON-AMERICAN-BOLLWORM-01 | SRC-TNAU-COTTON-BOLLWORM-01 | Yes | MATCH | F7 wording corrected: 12 options in source, 2 kept (subset, not complete). |
| AU-COTTON-PINK-BOLLWORM-01 | SRC-TNAU-COTTON-PINKBW-01 | **No — closed this audit** | MATCH | 3 options in source, all 3 kept (complete, not a subset). |
| AU-COTTON-SPOTTED-SPINY-BOLLWORM-01 | SRC-TNAU-COTTON-SPOTTEDBW-01 | Yes | MATCH | F7 wording corrected: 6 options in source, 3 kept (subset). |
| AU-RICE-YELLOW-STEM-BORER-01 | SRC-TNAU-RICE-STEMBORER-01 | Yes | MATCH | F7 wording corrected: 14 options in source, 3 kept (subset). Fipronil 5% SC gram-dose anomaly confirmed genuinely present in source. |
| AU-RICE-LEAF-FOLDER-01 | SRC-TNAU-RICE-LEAFFOLDER-01 | Yes | MATCH | F7 wording corrected: 9 options in source, 3 kept (subset). Chlorantraniliprole ml-vs-gram unit mismatch across two TNAU pages confirmed genuine (source inconsistency, not a transcription error). |
| AU-MAIZE-FALL-ARMYWORM-01 | SRC-TNAU-MAIZE-FAW-01 | **No — closed this audit** | MATCH | Seed treatment, both early-stage and late-whorl option sets, and the "Updated on May 2023" date all verbatim-confirmed. |
| AU-TOMATO-FRUIT-BORER-01 | SRC-TNAU-TOMATO-FRUITBORER-01 | Yes | MATCH | Description never claimed completeness; no F7 correction needed. "Updated on Jun, 2023" date confirmed. |
| AU-WHEAT-APHID-01 | SRC-NIPHM-DPPQS-WHEAT-01 | **No — closed this audit** | MATCH | Both chemical options for Aphids verbatim-confirmed; this record is complete (source lists exactly 2). |
| AU-WHEAT-TERMITE-01 | SRC-NIPHM-DPPQS-WHEAT-01 | Yes | MATCH | Deep ploughing, termitaria dismantling, neem cake dose, both seed-treatment options verbatim-confirmed. Foreword date (6.3.2014) not re-located in this pass's extracted text — flagged as a minor unresolved item, not a contradiction. |

**Result: 9/9 records MATCH. No fabricated or unsupported value was found anywhere in the dataset.** Two pre-existing dosage-unit oddities (Fipronil 5% SC dosed in grams; Chlorantraniliprole 18.5% SC dosed in ml on one TNAU page vs. grams on another) were re-confirmed as genuinely present in the sources themselves, not transcription artifacts — both remain flagged via `dosage_unit_note` rather than silently "corrected."

## 2. Safety-field (PHI/REI/PPE) coverage

**0 of 27 safety fields (9 records × 3 fields) are `PUBLISHED`.** No fetched TNAU page or the NIPHM/DPPQS wheat PDF publishes a pre-harvest interval, re-entry interval, or PPE requirement for any listed product. This was true in Phase 3 and remains true after this audit's live re-fetch — it is a genuine gap in the available public sources, not an omission on this project's part.

**Resolution (DEC-010, Decision 1):** this gap does not block Phase 4 classification (crop/pest labeling is independent of safety-field completeness). Instead, every record is now tagged with a computed `advisory_status`:

| advisory_status | Meaning | Current count |
|---|---|---|
| `ACTIONABLE_WITH_EVIDENCE` | Every chemical intervention has a fully PUBLISHED PHI+REI+PPE profile. Safe to present as an actionable recommendation. | 0 / 9 |
| `EDUCATIONAL_ONLY` | At least one safety field is unpublished (or the record has no chemical intervention at all). Retrievable for education/RAG context; must never be rendered as an actionable dose. | 9 / 9 |

A dedicated authoritative safety-data acquisition pass (e.g., locating CIB&RC product labels or other sources that do publish PHI/REI/PPE) remains an **explicitly open task**, required before Phase 6's Rule-Based Safety Engine can approve any record as `ACTIONABLE_WITH_EVIDENCE` in practice. Until then, `advisory_status` enforces the "educational retrieval, not actionable advice" boundary structurally, in the schema itself — not by convention.

## 3. Per-intervention safety restrictions (DEC-010, Decision 2)

`Intervention.safety_restrictions: Optional[SafetyRestrictions]` was added so a future source that publishes a *per-product* (not per-record) PHI/REI/PPE value can be recorded precisely — legally, PHI/REI attach to a specific registered product+label, not to an entire pest-management record that lists several interchangeable products.

- Defaults to `None`.
- **Never auto-populated** from the record-level `ApprovedUse.safety_restrictions` — confirmed by test (`test_existing_pilot_interventions_have_no_auto_populated_safety_restrictions`) that all 43 interventions across the 9 pilot records have `safety_restrictions is None`.
- `advisory_status` checks the intervention-level value first when present, falling back to the record-level value — tested explicitly (`test_advisory_status_uses_intervention_level_override_when_present`).
- The pre-existing record-level `ApprovedUse.safety_restrictions` field is **unchanged and still mandatory** — full backward compatibility confirmed (existing 9-record dataset reloads and all 28 original Phase 3 tests still pass unmodified).

## 4. F7 — misleading completeness wording, corrected

Phase 3 wording like *"recorded here exactly as the source groups them"* implied a kept chemical-option subset was the complete source list, when several records actually kept only 2–3 of the source's full list of interchangeable options. Five of six flagged `description` fields were rewritten with the verified option count and an explicit "subset, not the complete list" (or "complete, not a subset") statement:

| Record | Source option count | Kept in record | Previous wording | Corrected |
|---|---|---|---|---|
| AU-COTTON-AMERICAN-BOLLWORM-01 | 12 | 2 | Implied exhaustive | Explicit subset statement |
| AU-COTTON-SPOTTED-SPINY-BOLLWORM-01 | 6 | 3 | Implied exhaustive | Explicit subset statement |
| AU-RICE-YELLOW-STEM-BORER-01 | 14 | 3 | Implied exhaustive | Explicit subset statement |
| AU-RICE-LEAF-FOLDER-01 | 9 | 3 | Implied exhaustive | Explicit subset statement |
| AU-COTTON-PINK-BOLLWORM-01 | 3 | 3 (all) | N/A, already correct | Left unchanged — genuinely complete |
| AU-WHEAT-APHID-01 | 2 | 2 (all) | N/A, already correct | Left unchanged — genuinely complete |
| AU-TOMATO-FRUIT-BORER-01 | 8 | 4 | Never claimed completeness | Left unchanged — no F7 issue found |

Verified by test: `test_no_record_claims_to_be_an_exact_or_complete_source_grouping` asserts the old overstating phrases are absent from `approved_uses.json`.

## 5. F8 — schema validation gaps closed

| Gap | Phase 3 behavior | Phase 3.1 fix |
|---|---|---|
| Empty `interventions` list | Silently accepted | `ApprovedUse.interventions: list[Intervention] = Field(min_length=1)` — rejected at construction |
| `Source.publication_date = None` with no explanatory note | Only caught by a dataset-level test (`test_sources_without_explicit_publication_date_carry_a_note`) | New `model_validator` on `Source` rejects this at schema/construction level, same enforcement tier as the safety-field rules |
| Dead `SafetyField._value_required_if_published` validator | Asserted nothing, existed only as misleading documentation (the real rule lives in `SafetyRestrictions.model_post_init`) | Removed |

Both new rejections are covered by dedicated tests in `test_provenance_audit.py`.

## 6. Provenance manifest

[`knowledge_base/seed_data/provenance_manifest.json`](../knowledge_base/seed_data/provenance_manifest.json) — 9 entries, one per `approved_use_id`. Each entry carries:

- `source_url`, `retrieved_date` (2026-11-03), `fetch_method`
- `document_sha256` + `document_bytes` (integrity check — see explicit caveat below)
- `verbatim_excerpt` (the exact source text backing the record's values)
- `verdict` (`MATCH` for all 9) and human `notes`

Loaded via `backend/app/knowledge_base/provenance.py::load_provenance_manifest()`, a static, pre-computed loader with no network call at application startup — consistent with Phase 3's DB-independence design. Re-running the live audit (re-fetching every source and recomputing hashes) is a manual/CI step, not part of the request-serving path.

**Explicit integrity-vs-authenticity-vs-approval distinction (required by the user's additional instructions):**
- A SHA-256 hash in this manifest proves **integrity**: the bytes that were hashed are exactly the bytes whose text is quoted in `verbatim_excerpt`. Anyone can re-fetch `source_url` and recompute the hash to detect if the live page has since changed.
- It does **not** prove **authenticity** — that the fetched bytes genuinely and unalterably originated from the named authority in transit.
- It does **not** prove **regulatory approval** — that CIB&RC has certified the quoted product/crop/dose combination as a currently registered pesticide use.
- The only claim this project makes about any record is **source verification**: "we transcribed this text correctly from a named, fetchable page" (`verification_status: VERIFIED_SOURCE_RECOMMENDATION`). No record claims or implies CIB&RC registration/approval. This distinction is stated in `provenance.py`'s module docstring, in every record's `verification_note`, and now also on the frontend Knowledge Base page.

## 7. Files changed

| File | Change |
|---|---|
| `backend/app/knowledge_base/models.py` | Added `Source._publication_date_gap_must_be_explained` validator; removed dead `SafetyField` validator; `ApprovedUse.interventions` now `min_length=1`; added `Intervention.safety_restrictions` (optional); added `ApprovedUse.advisory_status` computed field. |
| `backend/app/knowledge_base/provenance.py` | **New.** `ProvenanceRecord`, `ProvenanceManifestError`, `load_provenance_manifest()`. |
| `backend/app/knowledge_base/__init__.py` | Exports extended with the new model/provenance symbols. |
| `backend/tests/test_provenance_audit.py` | **New.** 21 tests covering manifest shape/coverage, F7 wording removal, F8 schema rejections, `advisory_status` gating (default, override, non-chemical), per-intervention backward compatibility. |
| `knowledge_base/seed_data/approved_uses.json` | 5 intervention `description` fields corrected (F7); no dosage/value changed. |
| `knowledge_base/seed_data/provenance_manifest.json` | **New.** 9 audit entries. |
| `01_Blueprint/DECISION_LOG.md` | DEC-010 appended. |
| `docs/PHASE3_1_SAFETY_PROVENANCE_AUDIT.md` | **New** (this report). |
| `frontend/src/types/api.ts` | Added `Intervention.safety_restrictions` and `ApprovedUse.advisory_status` to stay in sync with the backend schema. |
| `frontend/src/pages/KnowledgeBase.tsx` | Replaced the hardcoded "Verified source recommendation" badge with an honest `advisory_status`-driven badge; added a page-level source-verification-vs-regulatory-approval notice. |

No existing file was deleted; no unrelated module was rewritten; no working feature was removed.

## 8. Test results

- `backend/tests/test_knowledge_base.py`: **28/28 passed** (all pre-existing Phase 3 tests, unmodified, no regressions).
- `backend/tests/test_provenance_audit.py`: **21/21 passed** (new).
- `backend/tests/test_health.py`: **4/4 passed** (unaffected, unmodified).
- **Full suite: 49/49 passed, 0 failed.**
- Frontend: `npm run build` (tsc -b && vite build) completed successfully — production bundle built with no type errors, including the new `advisory_status`/`safety_restrictions` fields.

## 9. Remaining limitations (honest, not hidden)

1. **0/27 safety fields published.** No currently used source publishes PHI, REI, or PPE for any pilot pest/product. Every record is `EDUCATIONAL_ONLY` until a dedicated acquisition pass (before Phase 6) finds an authoritative source that does.
2. **No per-product safety data yet.** The new `Intervention.safety_restrictions` field exists in the schema but is `None` on all 43 current interventions — no source fetched so far publishes a per-product value. This is intentional (never fabricate to fill the field) and is the expected state until the acquisition pass above succeeds.
3. **Authenticity, not just integrity, remains unverified.** The SHA-256 hashes confirm byte-for-byte integrity against this audit's own fetch; they do not independently prove the fetched content was never tampered with in transit, nor that it matches a CIB&RC-registered product (no live CIB&RC database lookup was accessible — unchanged from DEC-009).
4. **Minor unresolved item:** the wheat PDF's cited Foreword date (6.3.2014) was not re-located in this pass's extracted text (possibly a scanned/image page the text extractor skipped). This is flagged, not treated as a contradiction, since no conflicting date was found either.
5. **Static manifest, not live-checked.** The provenance manifest reflects a fetch on 2026-11-03; it is not re-verified automatically on every application start (by design, to preserve DB/network independence at load time). A future CI job re-running the audit script periodically would catch source-page drift; none exists yet.

## 10. Evidence the application still runs

- Backend: `pytest` → 49 passed, 0 failed (see §8).
- Backend: existing 9-record dataset reloads successfully through `JSONFileKnowledgeBaseRepository()` with the new schema, and `/knowledge-base/approved-uses/{id}` serves `advisory_status` and per-intervention `safety_restrictions` correctly (manually verified via `TestClient` against `AU-WHEAT-APHID-01`: `advisory_status: "EDUCATIONAL_ONLY"`, intervention `safety_restrictions` key present and `null`).
- Frontend: `npm run build` succeeds (tsc + vite), confirming the updated `api.ts` types and `KnowledgeBase.tsx` compile and bundle cleanly.
