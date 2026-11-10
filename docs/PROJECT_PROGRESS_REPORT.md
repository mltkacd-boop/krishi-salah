# Project Progress Report

**Project 26 — Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support**
Course: CSE 276 · Group Project
Report date: 2026-11-04
Current phase: **Phase 9 complete (deployment-readiness audit); deployment not started**

---

## 1. Where the project stands

The four required technical components are implemented and integrated end to end:
knowledge representation, supervised classification, retrieval-augmented generation and
rule-based reasoning, behind a bilingual agricultural advisory interface.

The system answers a farmer's question by classifying it, retrieving source-backed
passages, applying five deterministic safety rules, and composing an answer **only from
transcribed source fields**, with citations and an explicit decision class. It refuses,
restricts or escalates when a required safety value is missing — which, in the current
knowledge base, is always.

The project is **functionally complete and test-covered**. It is **not deployed** and is
**not yet ready for a public URL**; the four open blockers are listed in §8 and detailed in
[PHASE9_DEPLOYMENT_READINESS_AUDIT.md](PHASE9_DEPLOYMENT_READINESS_AUDIT.md).

---

## 2. Requirement coverage

| Required component | Implemented as | Evidence |
|---|---|---|
| Knowledge representation | 9 source-verified records, 5 crops, 8 sources, 43 interventions, explicit PHI/REI/PPE status per record, provenance manifest with URLs, retrieval dates and SHA-256 | `knowledge_base/seed_data/`, `app/knowledge_base/` |
| Supervised classification | Multi-head TF-IDF (word + character) + Logistic Regression for crop / task / safety-topic, English + Hindi + Romanized Hindi | `app/classification/`, `ml/classification/` |
| Retrieval-augmented generation | 384-dim deterministic lexical embeddings, exact cosine similarity in PostgreSQL, retrieve 20 → re-rank → filter → cite, **extractive** composition (no LLM) | `app/rag/`, `app/vector/` |
| Rule-based reasoning | R1–R5, six decision classes, block precedence, fails closed | `app/rules/` |
| Decision support UI | 5 routes, decision badges, confidence meter, safety disclosures, citations, EN/HI, error states | `frontend/src/` |

The assignment PDF is **not present in this workspace**, so compliance is stated against the
component list carried in the project handover, not re-read from the brief. No claim of full
assignment compliance is made here.

---

## 3. Phase status

| Phase | Deliverable | Status |
|---|---|---|
| 1 — Foundation | React + FastAPI, initial screens, API integration | complete |
| 2 — Architecture | Blueprint + decision log | complete |
| 3 — Knowledge base | 9 records, 5 crops, 8 sources, 43 interventions | complete |
| 3.1 — Safety & provenance audit | PHI/REI/PPE explicit, missing values never guessed, 9/9 `EDUCATIONAL_ONLY`, provenance hashes | complete |
| 4 — Supervised classification | 211-query dataset, multi-head model, held-out evaluation | complete |
| 5 — PostgreSQL | Local cluster (port 55432), 9 records, 60 chunks, exact cosine similarity | complete |
| 6 — RAG pipeline | `POST /rag/answer`, `GET /rag/status`, citations, EN/HI | complete |
| 7 — Rule-based reasoning | R1–R5, six decision types, regulatory-evidence gate, bypass fixed | complete |
| 8 — Frontend integration | 5 routes, decision badges, responsive, real API verified | complete, conditionally approved |
| 9 — Deployment readiness audit | Warnings reviewed, CORS/env/TLS hardening, frontend tests added, blockers documented | **complete — audit only** |

Phase 9 produced fixes and a gate, not a deployment. Nothing was deployed and no paid
account was created.

---

## 4. Current system figures (verified this run, from the data — not from the handover)

| Metric | Value |
|---|---|
| Knowledge records | 9 |
| Pilot crops | 5 (rice, wheat, maize, cotton, tomato) |
| Sources | 8 |
| Interventions | 43 |
| Search chunks | 60 |
| Records actionable | **0** |
| Records `EDUCATIONAL_ONLY` | 9 |
| Records with a published PHI value | 0 |
| Recorded regulatory verifications | 0 |
| Rules | 5 |
| Decision classes | 6 |

The zeros are the honest state, not a defect: no source in the pilot publishes PHI/REI/PPE
for the transcribed chemical interventions, and no CIB&RC registration check has been
performed. Completing safety fields without evidence is the one thing this project must
never do, so the advisory stays educational. This is why `ACTIONABLE_RECOMMENDATION` and
`REGULATORY_VERIFICATION_REQUIRED` cannot be demonstrated in the running app today — they
exist, are rule-reachable, and **have not been browser-tested**.

---

## 5. Model performance (held-out, n = 32)

| Target | Accuracy | Macro F1 |
|---|---|---|
| Crop | 84.38% | 0.835 |
| Task | 71.88% | **0.494** |
| Safety topic | 84.38% | 0.720 |

Read this carefully before quoting it: a 32-row test split is small, and the task head's
macro F1 of 0.49 means it handles some task classes markedly worse than its accuracy
suggests. The classifier is a routing aid that is **always** followed by rule gating and by
retrieval that requires a matched record; it is not a production-grade intent model, and the
report should not present it as one.

---

## 6. Verification status

| Check | Result |
|---|---|
| Backend test suite | 443 passed, 0 skipped, 0 failed |
| Frontend unit tests | 28 passed (added in Phase 9; none existed before) |
| Browser integration checks | 31/31 passed |
| Frontend production build | passes — 57 modules, 234.5 kB JS (73.5 kB gzip) |
| Secret scan | no secrets in committable files |

The backend figure requires the local PostgreSQL cluster to be running; without it the suite
reports 394 passed and 32 skipped, and every skip is a database test. Always start the
cluster before quoting a test count.

Demonstrated in the running application, against the real API:

| Question | Decision returned |
|---|---|
| Cotton pink bollworm | `EDUCATIONAL_INFORMATION` |
| Cotton pre-harvest interval | `SAFETY_REFUSAL` |
| Banana aphids | `CLARIFICATION_REQUIRED` |
| Sugarcane bollworm | `ESCALATION_REQUIRED` |
| Hindi: धान का तना छेदक | `EDUCATIONAL_INFORMATION` |

Client attempts to supply a decision, a safety value or regulatory evidence are rejected with
HTTP 422. That rejection, and the Phase 7 regulatory-bypass fix, are re-verified in the
current suite.

---

## 7. Known limitations (state these plainly in any review)

1. **No actionable advice is possible yet.** 0/9 records are actionable; the advisory can
   teach but cannot recommend, because the safety fields and registration checks do not exist.
2. **Two decision classes are unreachable in practice**, so they are visually implemented but
   not browser-tested.
3. **Retrieval is lexical, not semantic.** The 384-dim hashing embedder has no notion of
   synonymy and no cross-lingual ability. A Hindi pest name can return crop-level records
   instead of one matched record; the UI labels that case rather than guessing.
4. **Classifier task head is weak** (macro F1 0.49).
5. **No LLM.** Answers are assembled from record fields. That is a deliberate safety property,
   not an unfinished feature.
6. **pgvector is not verified.** Local storage uses `real[]` exact cosine scan; the pgvector
   branch has never run and is pinned off for deployment.
7. **No authentication, no rate limiting.** Blocking for a public URL.
8. **The API URL is baked in at build time**, so the deployed frontend needs
   `VITE_API_BASE_URL` set *and* a rebuild.
9. **The folder is not a git repository yet**, so it cannot be connected to a hosting provider.

---

## 8. What remains before deployment

In order, from the audit:

1. Initialise version control and push to a remote (blocker B1).
2. Set `VITE_API_BASE_URL` in Vercel and `CORS_ORIGINS` in Render to match, then rebuild (B2).
3. Decide the access model — public demo with quotas, or private evaluation with a token (B3).
4. Add rate limiting at the platform edge or in a shared-store middleware (B4).
5. Pin transitive dependencies from a clean install (B5).
6. Provision the cloud database, run migrations, import the knowledge base, verify with
   `VECTOR_STORAGE_MODE=array` (B6).
7. Point the platform health check at `/health`, not `/health/ready` (B8).

Recommended hosting: Vercel (frontend) + Render (backend) + Neon (PostgreSQL), all free tier.
The pilot's data footprint is kilobytes and PyTorch is no longer a dependency, so the free
tiers are a genuine fit rather than a compromise.

---

## 9. What can be defended in a viva

The design decisions a reviewer is most likely to probe, and the honest answer:

- **Why extractive answers instead of an LLM?** An LLM can invent a dose or a PHI value.
  Extractive composition cannot: every sentence comes from a transcribed field.
- **Why is nothing actionable?** Because PHI/REI/PPE and CIB&RC registration are not
  published for these interventions, and guessing them is the failure mode the project exists
  to prevent. The gate is working; the data is missing.
- **Why a lexical embedder?** Deterministic, offline, byte-reproducible similarity on a
  terminology-dense corpus, with no model download on an 8 GB laptop. Its limits are stated
  in the module docstring and in the UI.
- **Why does the frontend not decide anything?** The backend owns the decision, the client
  can only render it; unknown classes degrade to "unclassified", never to "actionable".
