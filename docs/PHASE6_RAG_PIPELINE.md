# Phase 6 — RAG Pipeline

**Decision record:** [DEC-013](../01_Blueprint/DECISION_LOG.md)
**Scope:** answer composition over the existing 9 records / 60 chunks, the Phase 4 classifier and the Phase 5 PostgreSQL store. No knowledge-base content was added or changed in this phase.

## What runs

```
POST /rag/answer  ->  classify -> embed -> retrieve -> rank -> decide -> compose -> cite
GET  /rag/status  ->  live backends, embedding model, thresholds
```

| Stage | Implementation |
|---|---|
| Query embedding | `HashingEmbeddingProvider` (`hashing-lexical-v1`, 384-dim, deterministic, offline) |
| Retrieval | Phase 5 store: exact `cosine_similarity()` scan over `embeddings` (`mode='array'`), 20 candidates |
| Ranking | `crop match +0.25 / mismatch −0.20`, pest-name alignment `+0.36 × Σ(1/df)` capped at `+0.45` |
| Attributability filter | chunks with no record, or whose record's source is missing, are dropped |
| Decision | Phase 4 classifier + crop agreement; PHI/REI/PPE and approval questions routed before pest alignment |
| Composition | extractive, from `ApprovedUse` fields only; `generation_mode: "extractive"` |
| Citations | grouped per source, with `reliability_tier`, `verification_status`, `provenance_sha256`, `record_ids` |

## Outcomes

`answered` · `needs_clarification` · `out_of_scope` · `unsupported_crop` · `insufficient_evidence` · `safety_value_not_published` · `no_regulatory_verification`

`answer` is null for every outcome except `answered`, and every answered response carries at least one citation and at least one evidence chunk.

## Verified behaviour (live API, PostgreSQL repository)

| Query | Outcome |
|---|---|
| `pink bollworm management in cotton` | answered, record scope, 1 citation, provenance present |
| `whitefly on cotton` | insufficient_evidence (no such record) |
| `bacterial blight in rice` | insufficient_evidence (no disease record; previously mis-answered) |
| `how long before I can harvest after spraying cotton` | safety_value_not_published |
| `is chlorpyriphos approved for rice in India` | no_regulatory_verification |
| `how do I fix my tractor engine` | out_of_scope |
| `saffron pest control` | unsupported_crop |
| `धान का तना छेदक` | answered, crop scope, 2 citations |

## Measurements that shaped the design

1. Similarity cannot gate: in-scope Hindi `धान का तना छेदक` = 0.111, out-of-scope `mandi price of rice today` = 0.311.
2. Raw similarity mis-assigns pest within a crop: pink-bollworm query ranked "Spotted bollworm / Spiny bollworm" first until rare-token weighting was added.
3. Crop words in the pest vocabulary cause cross-topic matches: "bacterial blight in rice" aligned to "Rice Leaf Folder" on the word "rice".
4. A Devanagari cotton query retrieves *maize* and *tomato* chunks, so crop-scope records come from the knowledge base, not from retrieval.

## Tests

`backend/tests/test_phase6_rag.py` — 42 tests, three groups: offline (JSON repository + in-memory store), HTTP surface, and PostgreSQL-backed end-to-end (skips with a reason when the database is not reachable). Full backend suite: **246 passed**.

## Limitations

- No generative model: answers are structured extracts, not prose; no follow-up dialogue.
- No semantic or cross-lingual embedding, so Hindi queries answer at crop level rather than matching a pest.
- Hindi output is Hindi scaffolding around English source values; crop names are localised, quoted source notes stay verbatim in English and are labelled as quotations.
- pgvector remains unverified on this machine (Phase 5 blocker, unchanged); search uses the exact array scan.
- No frontend surface for `/rag/answer` yet — the API and its tests are the Phase 6 deliverable.
