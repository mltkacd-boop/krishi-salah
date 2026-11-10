# Milestone 1 — Working Application Foundation
## Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support

**Student:** Himanshu Yadav | **Project Type:** Group Project
**Status:** Implemented and tested. Awaiting your review before Milestone 2.

---

## 1. Objective

Establish a working, verifiable application foundation: a FastAPI backend with real health/readiness checks, a
React+TypeScript+Tailwind frontend with the five required screens, and a connected frontend-backend-database-LLM
chain — without populating any agricultural knowledge yet (that is Phase 3).

Maps to: infrastructure for all three official objectives (Module A/UI, Module C/DB scaffold, Module F/LLM
provider interface). No classification, RAG, or rule-engine logic is implemented in this milestone — that remains
Phases 4–7, unchanged from the approved roadmap.

## 2. Conceptual Explanation

Think of this milestone as building the building's foundation, plumbing, and electrical wiring before adding
rooms (knowledge, intelligence, safety rules). The dashboard is a "control panel" that honestly reports whether
each dependency (database, vector extension, local AI model) is actually reachable — it never claims something
works unless it just checked.

## 3. Architecture (this milestone only)

```
React (Vite, :5173) --CORS--> FastAPI (uvicorn, :8000) --SQLAlchemy--> PostgreSQL 18 (:5432, local service)
                                      |
                                      +--HTTP--> Ollama (:11434) [not running in this environment]
```

- Frontend calls only `GET /health` and `GET /health/ready` in this milestone (Task 4 scope).
- Backend's `/health/ready` aggregates three real checks: DB connection, pgvector extension, LLM provider — never
  hardcoded.
- No agricultural data, classifier, retriever, or rule engine is wired in yet.

## 4. Technologies Used

| Layer | Technology | Version (installed) |
|---|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router | react 18.3, vite 5.4, tailwindcss 3.4 |
| Backend | FastAPI, Pydantic, Uvicorn | fastapi 0.115.0, pydantic 2.9.2 |
| DB driver | SQLAlchemy + psycopg2 | sqlalchemy 2.0.35 |
| ML/RAG deps (installed, not yet used) | scikit-learn, sentence-transformers | 1.5.2, 3.1.1 |
| LLM provider (installed, not yet used for generation) | Ollama client via `requests` | local Ollama, not running |
| Testing | pytest, httpx (FastAPI TestClient) | pytest 8.3.3 |

## 5. Implementation Summary

### 5.1 Workspace inspection (Task 1)
Found substantial **pre-existing Phase 2 scaffolding** already in the workspace before this milestone began:
`backend/app/main.py`, `app/api/health.py`, `app/core/config.py`, `app/db/connection.py`,
`app/advisory/llm_provider.py` (with a working `LLMProvider`/`OllamaProvider`/`CloudAPIProvider` abstraction),
`backend/requirements.txt`, `.env.example` files, and empty placeholder folders for the frontend
(`src/components`, `src/api`, `src/i18n`). All of this was preserved and extended, not overwritten.

### 5.2 Backend completed (Task 2)
Added (did not exist before):
- `app/schemas/health.py` — Pydantic response models (`LivenessResponse`, `ReadinessResponse`, etc.)
- `app/services/health_service.py` — aggregates DB/pgvector/LLM checks into one readiness computation
- Rewrote `app/api/health.py` to use the new schemas/service and add `GET /health/ready` (previously only
  `/health/full` existed)
- Rewrote `app/main.py` to add structured JSON error handling for `HTTPException` and unhandled exceptions, and
  widened CORS to also accept `127.0.0.1:5173`
- `backend/migrations/0001_enable_pgvector.sql` + `app/db/run_migrations.py` — minimal idempotent migration
  runner (tracks applied versions in `schema_migrations`), with clean (non-traceback) error reporting on failure
- `backend/tests/test_health.py` — 4 integration tests using FastAPI's `TestClient`
- `backend/pytest.ini`

Preserved unchanged: `app/core/config.py`, `app/db/connection.py`, `app/advisory/llm_provider.py`,
`requirements.txt`, `.env.example` (all already correct for this milestone's needs).

### 5.3 Frontend built (Task 3)
Built from the empty scaffold: Vite + React 18 + TypeScript + Tailwind, with:
- `src/layouts/AppLayout.tsx` + `src/components/Sidebar.tsx` — sidebar navigation, 5 routes
- Pages: `Dashboard.tsx`, `AdvisoryAssistant.tsx`, `KnowledgeBase.tsx`, `SafetyGuidelines.tsx`,
  `ProjectInfo.tsx` — the 4 non-Dashboard screens explicitly show "not yet implemented" placeholders rather than
  fake data, per the no-decorative-features / no-hardcoded-success rule
- `src/components/Card.tsx`, `PageHeader.tsx`, `StatusBadge.tsx` — reusable components
- Agricultural theme: deep green (`primary`) + amber (`warning`) + red (`danger`) palette in `tailwind.config.js`

### 5.4 Frontend-backend connection (Task 4)
- `src/services/apiClient.ts` — central fetch wrapper, typed `ApiError`, reads `VITE_API_BASE_URL`
- `src/services/healthService.ts` — typed calls to `/health` and `/health/ready`
- `src/hooks/useBackendHealth.ts` — polls real readiness; three states (`loading`/`success`/`error`); no
  hardcoded success message — if the backend is down, the Dashboard shows the actual fetch error text
- `src/types/api.ts` — response types mirrored from `backend/app/schemas/health.py`

### 5.5 Database foundation (Task 5)
- `backend/migrations/0001_enable_pgvector.sql` — `CREATE EXTENSION IF NOT EXISTS vector;` only
- `app/db/run_migrations.py` — applies migrations idempotently, tracks state, fails with a clear message (not a
  raw traceback) if the DB is unreachable
- **No agricultural tables created** — correct per instruction ("do not populate knowledge records yet")
- `backend/.env` configured to point at a `pesticide_app` role on `pesticide_advisory` DB — **this role does not
  exist yet** (see Pending Issues)

## 6. Input and Output

| Endpoint | Input | Output |
|---|---|---|
| `GET /health` | none | `{"status":"ok","service":"pesticide-advisory-backend"}` |
| `GET /health/ready` | none | `{"status":"ready"\|"degraded","database":{...},"pgvector":{...},"llm":{...},"supported_languages":["en","hi"]}` |
| Dashboard page | none (auto-fetches on load) | Live colored status badges for DB / pgvector / LLM, with raw error text on failure |

## 7. Testing (Task 6)

| Check | Method | Result |
|---|---|---|
| Backend unit/integration tests | `pytest -v` (4 tests) | **4 passed** |
| Frontend type-check + build | `npm run build` (`tsc -b && vite build`) | **Build succeeded**, 47 modules, no TS errors |
| Backend server starts | `uvicorn app.main:app` on :8000 | **Started successfully** |
| Frontend dev server starts | `npm run dev` (Vite) on :5173 | **Started successfully**, ready in ~2.7s |
| `GET /health` | `Invoke-RestMethod` | **200 OK**, `{"status":"ok",...}` |
| `GET /health/ready` | `Invoke-RestMethod` | **200 OK**, `status:"degraded"` (honest — DB/LLM both actually down, see below) |
| `GET /docs` (Swagger) | HTTP request | **200 OK** |
| CORS | Request with `Origin: http://localhost:5173` | `Access-Control-Allow-Origin: http://localhost:5173` header confirmed present |
| Frontend serving | HTTP request to `:5173` | **200 OK**, correct `<title>` in HTML |
| DB connectivity | `/health/ready` → `database` field | **Not connected** — see Pending Issues (expected, not a bug) |
| pgvector | `/health/ready` → `pgvector` field | **Not available** — same root cause (no DB connection) |
| Ollama / LLM | `/health/ready` → `llm` field | **Not available** — Ollama is not installed/running in this environment |
| Migration runner against unreachable DB | `python -m app.db.run_migrations` | Fails with a **clean, readable error message**, not a raw stack trace |

All results above are from actually executing the commands in this environment — none are simulated.

## 8. Actual Results

```json
GET /health
{ "status": "ok", "service": "pesticide-advisory-backend" }

GET /health/ready
{
  "status": "degraded",
  "database": { "connected": false, "message": "Database connection failed: ... password authentication failed for user \"pesticide_app\"" },
  "pgvector": { "connected": false, "message": "pgvector check failed: ... password authentication failed for user \"pesticide_app\"" },
  "llm": { "provider": "ollama", "available": false, "message": "Could not connect to Ollama server at http://localhost:11434. Is Ollama installed and running?" },
  "supported_languages": ["en", "hi"]
}
```

```
pytest -v
4 passed, 1 warning in 10.22s

npm run build
✓ 47 modules transformed.
✓ built in 3-5s (reproduced twice)
```

## 9. Presentation-Ready Explanation

"We built the skeleton of our system: a website (frontend) that talks to a server (backend), which in turn checks
whether our database and our local AI model are actually running — and tells the truth about it on screen, rather
than just saying everything is fine. Right now the database role and the AI model aren't set up yet in this
environment, and our dashboard correctly shows that as 'Degraded' instead of pretending otherwise. This is the
foundation Phases 3–7 will build the actual agricultural intelligence on top of."

### Possible viva questions
- **Q: Why does the Dashboard show "Degraded" instead of "Ready"?**
  A: Because the `pesticide_app` database role was never created (no superuser credentials were available) and
  Ollama isn't running in this environment. The system is designed to report real status, never a hardcoded
  "connected" message — this is itself a demonstration of the "no hardcoded success" requirement.
- **Q: Why is the knowledge base empty?**
  A: By explicit instruction for this milestone — populating verified pesticide records is Phase 3's job, and
  fabricating placeholder agricultural data would violate the project's core safety/accuracy rules.
- **Q: How is the LLM provider swappable?**
  A: `app/advisory/llm_provider.py` defines an abstract `LLMProvider` with `OllamaProvider` (default) and a
  `CloudAPIProvider` stub; `get_llm_provider()` selects based on the `LLM_PROVIDER` env var — no other module
  needs to change to add a cloud provider later.

## 10. Pending Issues (must be resolved before Milestone 2 / Phase 3)

1. **`pesticide_app` PostgreSQL role/database do not exist yet.** PostgreSQL 18 is installed and running as a
   Windows service, using `scram-sha-256` auth (no trust/peer access). I do not have the `postgres` superuser
   password and will not weaken `pg_hba.conf` without your explicit authorization. **Action needed from you:**
   either provide the postgres superuser password (one-time, to run the role/DB creation SQL below), or run it
   yourself:
   ```sql
   CREATE ROLE pesticide_app WITH LOGIN PASSWORD '<choose a real password>';
   CREATE DATABASE pesticide_advisory OWNER pesticide_app;
   ```
   Then update `backend/.env`'s `DATABASE_URL` with the real password and re-run
   `python -m app.db.run_migrations`.
2. **Ollama is not installed/running in this environment.** `/health/ready` correctly reports this rather than
   faking availability. Install from [ollama.com](https://ollama.com/download), then run
   `ollama pull llama3.2:3b` (or update `OLLAMA_MODEL` in `.env` to a model you prefer).
3. Once both are resolved, re-run `python -m app.db.run_migrations` and reload the Dashboard — it should show
   `"status": "ready"`.

## 11. How to Run

**Backend:**
```powershell
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
```

**Frontend:**
```powershell
cd frontend
npm run dev
# App: http://localhost:5173
```

**Tests:**
```powershell
cd backend
.venv\Scripts\python.exe -m pytest -v
```

**Migrations (after DB role exists):**
```powershell
cd backend
.venv\Scripts\python.exe -m app.db.run_migrations
```

## 12. Folder Structure (actual, as of this milestone)

```
backend/
  app/
    main.py                  [rewritten]
    api/health.py             [rewritten]
    schemas/health.py         [new]
    services/health_service.py [new]
    core/config.py            [preserved]
    db/connection.py           [preserved]
    db/run_migrations.py       [new]
    advisory/llm_provider.py   [preserved]
  migrations/0001_enable_pgvector.sql [new]
  tests/test_health.py         [new]
  pytest.ini                   [new]
  requirements.txt             [preserved]
  .env.example                 [preserved]
  .env                         [new, not committed]
  .venv/                       [new, not committed]

frontend/
  src/
    App.tsx, main.tsx, index.css, vite-env.d.ts   [new]
    layouts/AppLayout.tsx                           [new]
    components/{Sidebar,Card,PageHeader,StatusBadge}.tsx [new]
    pages/{Dashboard,AdvisoryAssistant,KnowledgeBase,SafetyGuidelines,ProjectInfo}.tsx [new]
    services/{apiClient,healthService}.ts           [new]
    hooks/useBackendHealth.ts                        [new]
    types/api.ts                                     [new]
    api/, i18n/                                      [preserved, empty — reserved for later phases]
  package.json, vite.config.ts, tailwind.config.js, postcss.config.js, tsconfig*.json [new]
  .env / .env.example                                [new/preserved]
```

No files outside `backend/` and `frontend/` were modified in this milestone.
