# Phase 2 Implementation Plan — Project Setup
## Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support

**Status of this document:** PROPOSED plan for review. Per your instruction, no scaffolding or code has been created yet. This plan is presented for approval before any files are generated.

**Legend used throughout:** ✅ COMPLETED | 🔲 PENDING (approved, not yet built) | 🅿️ PROPOSED (needs your review in this document)

---

## 1. What Is Completed vs. Pending vs. Proposed (Status Snapshot)

| Item | Status |
|---|---|
| Phase 1 architecture blueprint | ✅ COMPLETED (approved) |
| Decision log (geography, language, LLM, crops, team structure) | ✅ COMPLETED (approved) |
| Phase 2 setup plan (this document) | 🅿️ PROPOSED — awaiting your approval |
| Repository folder scaffolding | 🔲 PENDING — not created; will be created only after you approve this plan |
| Any backend/frontend/DB/ML/RAG code | 🔲 PENDING — nothing written |
| Knowledge base source research & data entry (Phase 3) | 🔲 PENDING — blocked on Phase 2 approval |
| Group member name assignment to roles | 🔲 PENDING — blocked on your member list |

---

## 2. Proposed Project Folder Structure

```
CSE276_PROJECT/
├── 01_Blueprint/
│   ├── PROJECT_ARCHITECTURE_BLUEPRINT.md      ✅ exists
│   └── DECISION_LOG.md                        ✅ exists
├── 02_Phase2_Setup/
│   └── PHASE2_IMPLEMENTATION_PLAN.md          ✅ this document
├── backend/                                    🔲 to be created on approval
│   ├── app/
│   │   ├── api/                 # FastAPI routers (query, admin/KB endpoints)
│   │   ├── classification/      # scikit-learn classifier wrappers (Module B)
│   │   ├── knowledge_base/      # DB models + repository functions (Module C)
│   │   ├── rag/                 # ingestion, chunking, embedding, retrieval (Module D)
│   │   ├── rules/               # rule classes + rule engine orchestrator (Module E)
│   │   ├── advisory/            # LLM provider interface + prompt templates (Module F)
│   │   ├── evaluation/          # logging + metrics scripts (Module G)
│   │   ├── core/                # config loader, settings, shared utils
│   │   └── main.py              # FastAPI app entrypoint
│   ├── migrations/              # SQL schema migrations (Section 9 schema)
│   ├── tests/                   # pytest unit + integration tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/                                    🔲 to be created on approval
│   ├── src/
│   │   ├── components/          # Answer, Evidence, ConfidenceBadge, EscalationBox
│   │   ├── i18n/                 # i18next config + locale files (en.json, hi.json)
│   │   ├── api/                  # backend API client
│   │   └── App.jsx
│   ├── package.json
│   └── .env.example
├── knowledge_base/                              🔲 to be created on approval
│   ├── sources/                  # curated source PDFs/text, one subfolder per source, with citation metadata
│   ├── seed_data/                 # CSV/JSON seed rows for products/crops/approved_use/safety_restriction
│   └── SOURCES_REGISTER.md        # human-readable authority/date/geography tracking for every source
├── ml/                                           🔲 to be created on approval
│   ├── datasets/                  # labeled query datasets (crop/task/safety-topic), per language
│   ├── notebooks/                 # exploratory training/evaluation notebooks
│   └── trained_models/            # serialized classifier artifacts (.joblib), git-ignored if large
├── docs/                                         🔲 to be created on approval
│   ├── chapters/                  # Ch01–Ch12 academic report sections (living documents)
│   └── diagrams/                  # exported architecture/DFD/UML images
├── docker-compose.yml                            🔲 to be created on approval
├── .gitignore                                    🔲 to be created on approval
└── README.md                                     🔲 to be created on approval
```

**Design rationale:** one top-level folder per module group (not per the A–G letter codes directly, but mapped 1:1 inside `backend/app/`), so grading/viva reviewers can trace each folder to Section 7 of the blueprint. `knowledge_base/` and `ml/datasets/` are kept outside `backend/` because they are *data*, not code — this matters for the "do not fabricate data" rule: these folders are where source traceability lives and will be reviewed for authenticity.

---

## 3. Frontend Setup (Proposed)

- **Stack:** React + Vite, i18next for localization.
- **Initial locales:** `en` (English), `hi` (Hindi) — each a JSON namespace file; adding a third language later means adding `<lang>.json` + a language-selector entry only.
- **Core screens for the pilot:** single query screen with language selector, submit box, and the four always-visible result zones (Answer / Evidence / Confidence badge / Escalation box) as defined in blueprint §7A.
- **Install (once scaffolded):**
  ```
  cd frontend
  npm install
  npm run dev
  ```
- **Environment variables (`frontend/.env.example`):**
  ```
  VITE_API_BASE_URL=http://localhost:8000
  ```

## 4. Backend Setup (Proposed)

- **Stack:** Python 3.11+, FastAPI, Uvicorn.
- **Install (once scaffolded):**
  ```
  cd backend
  python -m venv .venv
  .venv\Scripts\Activate.ps1        # PowerShell on Windows
  pip install -r requirements.txt
  uvicorn app.main:app --reload --port 8000
  ```
- **Proposed `requirements.txt` contents (by module):**
  - FastAPI, uvicorn, pydantic-settings — API layer
  - psycopg2-binary / SQLAlchemy — PostgreSQL access (Module C)
  - scikit-learn, joblib — classification (Module B)
  - sentence-transformers, pgvector (Python client) — RAG (Module D)
  - requests (or `ollama` Python client) — Ollama integration (Module F)
  - pytest, pytest-cov — testing

## 5. Database Setup (Proposed)

- **Stack:** PostgreSQL 15+ with the `pgvector` extension enabled.
- **Local setup via Docker (recommended for consistency across team members' machines):**
  ```
  docker run --name pesticide-db -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?export this in your shell; never commit it}" `
    -e POSTGRES_DB=pesticide_advisory -p 5432:5432 -d pgvector/pgvector:pg15
  ```
- **Migrations:** the Section 9 schema (products, crops, sources, approved_use, safety_restriction, query_log, rule_decision_log, kb_chunks) will be written as numbered SQL migration files in `backend/migrations/`, applied in order. No seed data beyond 1–2 clearly-labeled example rows will be added at scaffolding time — real data entry is Phase 3.
- **Geography/authority enforcement (per DEC-002):** `sources.geography` and `sources.authority` will be `NOT NULL` constraints at the DB level, not just convention.

## 6. ML Environment Setup (Proposed)

- Same Python virtualenv as backend (`backend/.venv`) — no separate ML environment, to avoid dependency-sync drift between the classifier and the serving API that uses it.
- `ml/notebooks/` is for exploratory training only; the final classifier training script will be a plain `.py` script under `backend/app/classification/train.py` so training is reproducible outside a notebook.
- Trained model artifacts saved to `ml/trained_models/*.joblib`, loaded by the FastAPI app at startup.

## 7. RAG Environment Setup (Proposed)

- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (supports both English and Hindi, per DEC-003) — downloaded once and cached locally (no per-call API cost).
- Ingestion script (`backend/app/rag/ingest.py`) reads curated files from `knowledge_base/sources/`, chunks text, embeds, and writes to the `kb_chunks` table via pgvector.
- Retrieval function (`backend/app/rag/retrieve.py`) performs top-k cosine similarity search, optionally filtered by classifier-predicted crop/product.

## 8. Ollama Integration (Proposed, per DEC-004)

- **Local install (team members, once approved):**
  ```
  # Install Ollama from https://ollama.com (one-time, per machine)
  ollama pull <model-name-to-be-finalized-in-phase-7>
  ollama serve
  ```
  *(Exact model name — e.g., a small instruction-tuned model suitable for paraphrasing — will be finalized in Phase 7 based on team hardware constraints; it will be recorded as a DEC-0XX entry when chosen, not assumed now.)*
- **Integration point:** `backend/app/advisory/llm_provider.py` defines the `LLMProvider` interface; `OllamaProvider` implements it via local HTTP calls to the Ollama server (default `http://localhost:11434`).
- **Provider-agnostic contract:**
  ```
  class LLMProvider(ABC):
      def generate(self, prompt: str, language: str) -> str: ...

  class OllamaProvider(LLMProvider):
      # calls local Ollama HTTP API
  ```
  A future `CloudAPIProvider(LLMProvider)` can be added later (Phase 7+ or post-pilot) by implementing the same method — no change needed to Modules B–E or to how F constructs prompts.
- **Environment variable:** `LLM_PROVIDER=ollama` (switchable to `cloud` later) and `OLLAMA_BASE_URL=http://localhost:11434` in `backend/.env`.

## 9. Security and Environment Configuration (Proposed)

- `backend/.env` (git-ignored) holds: `DATABASE_URL`, `LLM_PROVIDER`, `OLLAMA_BASE_URL`, and (reserved for later) `CLOUD_LLM_API_KEY`.
- `backend/.env.example` committed to the repo with placeholder values only, documenting required variables without real secrets.
- `.gitignore` excludes: `.env`, `.venv/`, `node_modules/`, `ml/trained_models/*.joblib` (if large), `__pycache__/`.
- DB access role for the API: least-privilege, read/write only on the `pesticide_advisory` application schema (per blueprint §14).
- No personal/farmer data collection in the pilot; query logs store the query text, language, and classification/rule outcome only.

## 10. Installation and Execution Instructions (Proposed, End-to-End)

```
# 1. Clone/open the repository (already in place: C:\Users\asus\Documents\CSE276_PROJECT)

# 2. Start the database
docker run --name pesticide-db -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?export this in your shell; never commit it}" `
  -e POSTGRES_DB=pesticide_advisory -p 5432:5432 -d pgvector/pgvector:pg15

# 3. Apply schema migrations
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app/db/run_migrations.py      # applies Section 9 schema

# 4. Start Ollama (separate terminal)
ollama serve
ollama pull <model-name>

# 5. Start the backend API
uvicorn app.main:app --reload --port 8000

# 6. Start the frontend (separate terminal)
cd frontend
npm install
npm run dev

# 7. Open the app
# Frontend: http://localhost:5173  (Vite default)
# Backend API docs: http://localhost:8000/docs  (FastAPI auto-generated)
```

*(Exact script names/paths above are illustrative of the proposed structure; final filenames will be fixed when scaffolding is actually created, after your approval.)*

---

## 11. Changes Required to the Architecture Because of These Decisions (Section C of your request)

| Change | Reason | Where Documented |
|---|---|---|
| Add explicit `LLMProvider` interface in Module F | Needed to satisfy "provider-independent, cloud API addable later" requirement (DEC-004) | Blueprint §7F (updated), this plan §8 |
| Enforce `sources.geography` / `sources.authority` as NOT NULL at DB level | India/CIB&RC-only scope must be structurally enforced, not just a convention (DEC-002) | Blueprint §9 (schema), this plan §5 |
| Language fields treated as extensible codes, not a fixed English/Hindi enum | "Additional Indian languages can be added later" requirement (DEC-003) | Blueprint §13 (updated) |
| Pilot KB success metric reframed as "records verified" not "records count" | Prevents pressure to fabricate records to hit 10–20 (DEC-005) | Blueprint §4.4 (updated), Decision Log DEC-005 |
| New `knowledge_base/SOURCES_REGISTER.md` artifact added to planned structure | Needed to track authority/date/geography per source transparently for grading (master prompt §5, items 1–2, 8) | This plan §2 |
| New risk tracked: Ollama local inference latency/quality on team hardware | Introduced by DEC-004; wasn't a risk when provider was undecided | Blueprint §18 risk table (to be updated at Phase 7 when model is chosen) |

No other changes to the Phase 1 architecture (component list, data flow, rule-engine gating order, DB schema core entities) are required — the approved decisions fit within the existing design.

---

## 12. Module-Wise Responsibility Matrix (Section E of your request — Placeholders Only)

> Names intentionally left unassigned, per your instruction, until the complete group member list is provided. Replace `Member [A–E] — unassigned` once names are available.

| Module | Maps to Objective | Primary Owner (placeholder) | Secondary/Support (placeholder) | Key Deliverables |
|---|---|---|---|---|
| A. User Interface (React + i18next) | Obj. 3 | Member [A] — unassigned | Member [B] — unassigned | Query screen, 4 result zones, language selector |
| B. Query Processing / Classification | Obj. 2 | Member [B] — unassigned | Member [C] — unassigned | Labeled dataset, trained classifiers, evaluation report |
| C. Knowledge Representation (DB + KB data) | Obj. 1 | Member [C] — unassigned | Member [D] — unassigned | Schema migrations, verified source research, seed data, SOURCES_REGISTER.md |
| D. RAG Module | Obj. 2 & 3 | Member [D] — unassigned | Member [E] — unassigned | Ingestion/chunking/embedding pipeline, retrieval evaluation |
| E. Rule-Based Safety Engine | Obj. 2 | Member [E] — unassigned | Member [A] — unassigned | Rule classes, safety test case suite, pass/fail report |
| F. AI Advisory Module (incl. Ollama integration) | Obj. 3 | Member [A] — unassigned | Member [C] — unassigned | LLMProvider interface, OllamaProvider, prompt templates |
| G. Evaluation & Monitoring + Testing (Ch.10) | All | Member [D] — unassigned | Member [B] — unassigned | Logging, metrics scripts, full test suite execution |
| Documentation (Ch.01–12) & Presentation | All | Shared — rotating owner per chapter | All members review | Living `docs/chapters/` files, final presentation deck |

**Note:** this is a *structural* proposal (which module needs which kind of skill — e.g., frontend, ML, data curation, backend/rules) — not a workload-balance guarantee. Once you provide the member list and their skill preferences, the matrix can be finalized with actual names and adjusted for balance.

---

## 13. Twelve-Chapter Documentation Structure (Maintained, Unchanged)

Chapters 01–12 as defined in the master prompt are preserved exactly:
01 Project Introduction · 02 Objectives and Requirements · 03 Technology Stack · 04 System Architecture · 05 Knowledge Representation · 06 Supervised Classification · 07 Retrieval-Augmented Generation · 08 Rule-Based Reasoning · 09 Multilingual Advisory Interface · 10 Testing and Evaluation · 11 Final Project Outcome · 12 Future Scope and Conclusion.

Each will live as a living document under `docs/chapters/Ch0X_<name>.md`, updated incrementally as each phase completes — not written all at once at the end.

## 14. Ten (Eleven-Listed) Implementation Phases (Maintained, Unchanged)

The master prompt's phase sequence is preserved exactly and is being followed in order:

| Phase | Status |
|---|---|
| 1 — Requirements and Architecture | ✅ COMPLETED (approved) |
| 2 — Technology Stack and Project Setup | 🅿️ PROPOSED (this document — awaiting approval; no scaffolding created yet) |
| 3 — Agricultural Knowledge Base | 🔲 PENDING |
| 4 — Supervised Classification | 🔲 PENDING |
| 5 — RAG Pipeline | 🔲 PENDING |
| 6 — Rule-Based Safety Engine | 🔲 PENDING |
| 7 — AI Advisory Integration | 🔲 PENDING |
| 8 — Multilingual Interface | 🔲 PENDING |
| 9 — Testing and Evaluation | 🔲 PENDING |
| 10 — Deployment | 🔲 PENDING |
| 11 — Final Documentation and Presentation | 🔲 PENDING |

No phase will be skipped; no module will be implemented until its preceding phase's plan is reviewed, per your explicit instruction.

---

## 15. What Happens After You Approve This Plan

Once approved, the next concrete action (and only that action, not all modules at once) will be:
1. Create the folder scaffolding in Section 2 (empty structure + placeholder config files).
2. Write the Section 9 schema as runnable SQL migrations, with 1–2 clearly-labeled example rows only (no real pilot data yet).
3. Set up `.env.example` files and `docker-compose.yml`.
4. Stop and present the result for review before moving into Phase 3 (real knowledge base data curation).

**This document itself makes no changes to the filesystem. Awaiting your approval before any file/folder scaffolding is created.**
