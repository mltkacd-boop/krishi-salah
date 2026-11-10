# Krishi Salah — Safe Pesticide Use Knowledge and Advisory Assistant

A decision-support assistant for Indian farmers that answers questions about a crop,
a pest, or a pesticide safety rule **only** from transcribed, cited sources, and then
refuses, restricts or escalates whenever the safety data needed for a
recommendation is missing.

Krishi Salah ("agriculture advice") is an **educational pilot**. It is not a
pesticide recommendation service, not a regulatory approval system, and not a
substitute for the product label.

---

## What it does

- Answers questions about pests and pesticide safety for five crops: **rice,
  wheat, maize, cotton and tomato**.
- Retrieves evidence from a small, hand-transcribed knowledge base of published
  Indian agricultural sources (state agricultural universities and national
  institutes), and assembles the answer **extractively** — quoted from the
  sources, never generated.
- Runs a deterministic rule engine over the matched record **before** any answer
  is written. The rules decide whether the response is an educational
  explanation, a clarification request, a refusal, an escalation, or a verified
  recommendation.
- States, prominently, which safety fields are missing (pre-harvest interval,
  re-entry interval, protective equipment, regulatory registration) instead of
  guessing or omitting them.
- Shows every source with its authority, publication date where the source
  publishes one, a reliability tier and an outbound link.
- Speaks English and Hindi, and accepts a question in either.
- Separates the farmer-facing interface from an evaluation view: machine-readable
  decisions, rule identifiers, retrieval scores and model versions live behind a
  labelled "Technical details" disclosure and a separate `/evaluation` page.

## Architecture

```
React + TypeScript (Vite)          FastAPI
  pages / components        ──►      /rag/answer  ──►  retrieval  ──►  rule engine  ──►  response
  services (typed client)            /knowledge-base      (lexical,      (R1–R5,          (answer, decision,
  i18n (EN, HI)                      /classification       TF-IDF        deterministic)    evidence, citations,
                                     /rules, /health                       block precedence)  safety disclosures)
                                            │
                                            ▼
                                    PostgreSQL  — knowledge base records, sources,
                                    provenance manifest, schema migrations
```

Three safety properties are structural, not stylistic:

1. **The frontend cannot choose a decision.** The request schema forbids unknown
   fields, and no control sets `decision`, `outcome` or `advisory_status`.
2. **Evidence is mandatory for an actionable answer.** A record can only become
   `ACTIONABLE_WITH_EVIDENCE` when every chemical intervention has a *published*
   PHI, REI and PPE value and a recorded CIB&RC registration check. No record in
   the current pilot meets that bar, so every chemical answer is educational.
3. **Generation is extractive.** There is no LLM in the serving path; the answer
   is composed from retrieved passages, so a dosage cannot be invented.

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, TypeScript 5, Vite 5, Tailwind CSS 3, React Router 6 |
| Frontend tests | Vitest 2, Testing Library, jsdom |
| Backend | Python 3.12, FastAPI 0.115, Pydantic 2, SQLAlchemy 2, Uvicorn |
| Database | PostgreSQL 18 (schema in `backend/migrations`) |
| Classification | scikit-learn 1.5 (TF-IDF + logistic regression), joblib |
| Retrieval | Deterministic lexical hashing embedder (`hashing-lexical-v1`), exact cosine scan over `real[]` |
| End-to-end checks | Playwright driving the installed Microsoft Edge |

## Repository layout

```
frontend/            React application
  src/pages          Home, Ask assistant, Knowledge library, Safety guide,
                     About, Evaluation
  src/components     Result rendering, decision badge, error boundary
  src/services       Typed API client wrappers
  src/i18n           English and Hindi strings
backend/
  app/api            HTTP routes
  app/rag            Retrieval, evidence assembly, extractive composition
  app/rules          Deterministic rule engine and regulatory verification
  app/classification Classifier wrapper + committed artifact
  app/db             Connection, migrations, knowledge-base import
  migrations         Hand-written SQL, applied in filename order
  tests              pytest suite
  scripts            Screenshot, integration and presentation checks
knowledge_base/
  seed_data          crops, sources, approved uses, provenance manifest
  sources            Source register
ml/classification    Training scripts, dataset, metrics, evaluation report
docs/                Phase reports and audits
scripts/             Database provisioning and secret audit
```

Two things are deliberately **not** in version control, though they exist in a
working copy: `docs/phase3_1_audit_raw/` (the raw fetched source pages and their
hashes, kept locally as provenance evidence — the manifest and register that cite
them are tracked) and `backend/probe_phase7.py` (a one-off diagnostic probe, not
imported by the app, the tests or any script).

## Prerequisites

- Python **3.12** (the backend virtual environment was built with 3.12.2)
- Node.js **22** with npm (built and tested with 22.23.2)
- PostgreSQL **18** if you want the database-backed mode; a project-local cluster
  is provisioned by a script, so a system installation is optional

## Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional semantic embeddings are **not** installed by default — the lexical
embedder is the default and needs no model download. If you want the optional
provider, see `backend/requirements-optional.txt`.

Copy `backend/.env.example` to `backend/.env` and set the values (see
[Environment configuration](#environment-configuration)). Then:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health endpoints: `GET /health`, `/health/ready`, `/health/db`, `/health/pgvector`,
`/health/llm`.

## Frontend setup

```powershell
cd frontend
npm ci
npm run dev            # http://127.0.0.1:5173
```

Copy `frontend/.env.example` to `frontend/.env` if the API is not on
`http://localhost:8000`.

## Database setup and migrations

The repository ships a provisioning script that creates a project-local
PostgreSQL cluster under `.pgdata/` with a generated application password, and
writes the resulting `DATABASE_URL` into `backend/.env`. Nothing about that
cluster is committed.

```powershell
# from the repository root, with the backend venv
.\backend\.venv\Scripts\python.exe scripts\setup_database.py --init-local-cluster
.\backend\.venv\Scripts\python.exe scripts\setup_database.py --start
.\backend\.venv\Scripts\python.exe scripts\setup_database.py --status
.\backend\.venv\Scripts\python.exe scripts\setup_database.py --verify
```

To use an existing PostgreSQL server instead, use `--existing` (it prompts for the
admin password) or simply point `DATABASE_URL` at your own database.

Apply the schema — three hand-written migrations, tracked idempotently in a
`schema_migrations` table:

```powershell
cd backend
python -m app.db.run_migrations
```

Load the knowledge base from `knowledge_base/seed_data`:

```powershell
python -m app.db.import_knowledge_base
```

`0001_enable_pgvector.sql` is optional in practice: the default storage mode is
`array`, and the pgvector path has **not** been verified on this deployment (see
[Known limitations](#known-limitations)).

## Environment configuration

All values are read from the environment or from the app-local `.env`; nothing is
hardcoded and no credential is committed. `backend/.env.example` documents the
configurable keys with placeholders. `DB_SSLMODE` and `CORS_ORIGINS` are read too,
but they have safe defaults (empty, and localhost) so the example does not list
them.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string (placeholder in the example) |
| `DB_SSLMODE` | TLS mode for managed databases (blank for local) |
| `KB_REPOSITORY` | Knowledge-base repository backend |
| `VECTOR_STORE` | `array` (default) or `pgvector` |
| `EMBEDDING_PROVIDER` | `hashing` (default) or the optional semantic provider |
| `LLM_PROVIDER` | `none` by default; the serving path is extractive |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Only used if a local LLM provider is selected |
| `CLOUD_LLM_API_KEY` | Empty in the example; a real key must never be committed |
| `APP_ENV`, `LOG_LEVEL` | Runtime environment and log level |
| `SUPPORTED_LANGUAGES` | Interface/answer languages |
| `CORS_ORIGINS` | Allowed frontend origins; `*` is refused |

`frontend/.env` takes a single key: `VITE_API_BASE_URL`.

## Tests

```powershell
# backend — 443 tests
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# frontend — 75 tests
cd frontend
npx vitest run
npx tsc --noEmit
npm run build

# repository secret audit (read-only, masks values)
.\backend\.venv\Scripts\python.exe scripts\audit_secrets.py
```

End-to-end checks (require the API on `:8000` and Vite on `:5173`):

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\phase9_integration_check.py    # 31 assertions
.\.venv\Scripts\python.exe scripts\presentation_check.py          # 59 assertions
```

## Known limitations

- **Nothing is actionable yet.** 0 of 9 pilot records publish a pre-harvest
  interval, a re-entry interval and a protective-equipment requirement together,
  so every chemical answer is educational. `ACTIONABLE_RECOMMENDATION` and
  `REGULATORY_VERIFICATION_REQUIRED` are consequently unreachable in this build.
- **The CIB&RC registry is never queried.** No automated regulatory check exists;
  the assistant tells the user to verify the registration number on the label.
- **The knowledge base is deliberately small.** Nine approved-use records across
  five crops. Questions outside that scope are escalated rather than answered.
- **Retrieval is lexical.** Questions are matched on words, not meaning, so a
  Hindi question is matched against English source text; common phrasings work,
  unusual ones can be missed.
- **pgvector is unverified.** The `array` storage mode and exact cosine scan are
  what runs; the pgvector path exists in migration `0003` but has not been
  validated on a deployment.
- **No LLM is used for answering.** Composition is extractive by design; any
  future LLM layer must remain unable to originate pesticide facts.
- **No deployment is configured or claimed.** The repository contains a
  `frontend/vercel.json` for a static build only; no hosted environment is
  described here because none has been verified.

## Safety disclaimer

This project is an academic pilot for decision support. It does **not** provide
pesticide dosage recommendations, does **not** certify that any product is
registered or approved for a given crop and pest, and does **not** replace the
product label or a licensed agronomist. Where a safety value is not published in
the source, the assistant says so and withholds the recommendation. Always read
the product label, and confirm the registration number with the Central
Insecticides Board & Registration Committee (CIB&RC) before buying or spraying
anything.

## Privacy

The farm-facing interface carries no personal or submission metadata. Student
names and registration numbers are not committed to this repository; the tests
that assert their absence are intentional and must not be weakened.
