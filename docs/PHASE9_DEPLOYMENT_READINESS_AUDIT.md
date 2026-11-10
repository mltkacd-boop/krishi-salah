# Phase 9 — Deployment Readiness Audit

Audit date: 2026-11-04
Scope: deployment readiness only. No deployment, no paid account, no change to any
safety rule, threshold, decision class or knowledge-base record.
Status: **audit complete; deployment NOT started.**

---

## 1. Verdict

The application is **technically deployable** but is **not ready for a public URL**.
Two blockers are configuration (version control + API URL/CORS alignment), and one is a
genuine security gap (no authentication or rate limiting on an unauthenticated,
compute-per-request endpoint).

| Area | State after this audit |
|---|---|
| Backend test suite | 443 passed, 0 skipped, 0 failed |
| Frontend unit tests | 28 passed (new; previously none existed) |
| Browser integration checks | 31/31 passed (new automated script; previously manual screenshots) |
| Frontend production build | passes, 57 modules, 234.5 kB JS / 73.5 kB gzip |
| Secret scan | no secrets in committable files |
| CORS | now environment-driven; wildcard refused |
| Cloud PostgreSQL | supported (TLS + storage-mode pin), but **not tested against a managed instance** |
| Authentication | **absent — blocker** |
| Rate limiting | **absent — blocker** |
| Version control | **no git repository in the project folder — blocker** |

The handover's "426 tests passed" is correct **only when the local PostgreSQL cluster is
running**. On a cold machine the suite reports `394 passed, 32 skipped`: every skipped test
is a Phase 5 integration test that requires the database. That is a reporting trap, not a
code defect, and it is why this audit starts the cluster before trusting any number.

---

## 2. Baseline confirmed (not rebuilt)

Verified against the files, not the handover:

- 5 routes (`/`, `/advisory`, `/knowledge-base`, `/safety-guidelines`, `/project-info`).
- 9 knowledge records, 5 pilot crops, 8 sources, 60 indexed chunks (`/rag/status`).
- 5 deterministic rules exposed by `/rules/status`; `0 of 9` records actionable.
- Both unproducible UI classes (`ACTIONABLE_RECOMMENDATION`,
  `REGULATORY_VERIFICATION_REQUIRED`) still cannot be produced by the data — unchanged,
  and still **not** browser-tested. This audit did not fabricate a state for them.
- Extractive generation only; no LLM is called and none is required.

---

## 3. Actual fixes made

Each fix is small, reversible, and outside the safety path.

### 3.1 CORS is now configuration, not code (`backend/app/core/config.py`, `app/main.py`)

Before, the allowed origins were two hardcoded localhost strings with
`allow_credentials=True` and `allow_methods=["*"]`. A Vercel frontend could not be added
without editing source.

Now: `CORS_ORIGINS` (comma-separated, exact origins) drives the middleware.
`allow_credentials` is off (no cookies are used), methods are limited to
`GET, POST, OPTIONS`, headers to `Content-Type`. `CORS_ORIGINS=*` raises at startup instead
of being accepted, and `APP_ENV=production` with loopback-only origins logs a warning — the
warning fired correctly during the audit.

### 3.2 Managed-PostgreSQL TLS (`config.py`, `app/db/connection.py`)

`DB_SSLMODE` is passed to psycopg2 only when set. Empty means "libpq default", so the local
cluster behaves exactly as before. A blank value is never forwarded as `sslmode=''`, which
libpq rejects.

### 3.3 Vector storage mode can be pinned (`app/vector/store.py`)

Migration 0003 records what the *database* supports. On Neon or Render, pgvector is
available, so the app would silently switch production onto the **pgvector branch, which
no test in this project has ever executed** (locally the array branch runs).

`VECTOR_STORAGE_MODE=array|pgvector|auto` now pins the branch. `array` forces the exact
`cosine_similarity()` scan, which exists on every PostgreSQL build. `pgvector` where the
database has no extension raises a clear error instead of quietly degrading. Default stays
`auto`, so nothing changes for the current local setup.

### 3.4 Oversized request cap (`app/main.py`)

An unauthenticated endpoint accepted any body size. A 16 KB `Content-Length` cap now returns
a structured 413 before the pipeline runs. It is placed *inside* the CORS layer so the 413
keeps its CORS headers. Known limitation, stated rather than hidden: only `Content-Length` is
checked; a chunked body without that header is caught later by Pydantic's
`max_length=1000`.

### 3.5 Accessibility: document language (`frontend/src/i18n/LanguageProvider.tsx`)

The browser integration check found `<html lang="en">` while the interface was Hindi, because
`index.html` ships a static attribute. The provider now sets `document.documentElement.lang`
on change. Found by a test, not by inspection.

### 3.6 Unknown decision classes no longer print an i18n key (`components/DecisionBadge.tsx`)

A decision value the build does not recognise rendered the raw key
(`decision.SOMETHING_NEW`) because the lookup returned the fallback key. It now renders as
unclassified, keeps the backend value in `data-decision`, and cannot borrow the
ACTIONABLE styling. This is the "must never silently become an approval" property, now
tested.

### 3.7 Deployment artefacts and dependency split

- `backend/requirements.txt`: removed `sentence-transformers`. It pulls PyTorch (~2 GB) and is
  imported lazily; the default provider is the deterministic hasher. A hosting plan should not
  pay build time and RAM for a code path the deployment never runs.
- `backend/requirements-optional.txt`: `sentence-transformers`, `playwright` (both optional;
  the Playwright pin matches the installed 1.64.1).
- `backend/.env.example`: documents `DB_SSLMODE`, `CORS_ORIGINS`, `VECTOR_STORAGE_MODE` and
  the real cloud values.
- `frontend/vercel.json`: SPA rewrite so `/advisory` and the other client routes resolve on
  direct navigation, plus `nosniff` / `X-Frame-Options` / `Referrer-Policy` and immutable
  asset caching. JSON parses; **the Vercel behaviour itself is not verified** (nothing was
  deployed).
- `backend/scripts/phase9_integration_check.py`: the Phase 8 screenshot walkthrough, converted
  into 31 assertions that exit non-zero. `phase8_screenshots.py` and `overflow_check.py` are
  untouched and still work.

---

## 4. Test results (this run)

```
backend   python -m pytest -q            -> 443 passed, 71 warnings (11 when grouped), 0 skipped, ~40 s
frontend  npm test                       -> 28 passed (4 files)
frontend  npm run build                  -> tsc -b + vite build OK, 57 modules
browser   phase9_integration_check.py    -> 31/31 checks passed
secrets   scripts/audit_secrets.py       -> no secrets in committable files
```

Backend coverage added (15 + 2 tests in `tests/test_phase9_deployment_config.py`): CORS
defaults/override/wildcard-free/credentials-off, preflight header behaviour, `APP_ENV`
handling, `sslmode` presence and blank handling, storage-mode pin (all four outcomes),
request-size cap, and readiness honesty.

Frontend coverage added (28 tests): API client success, `{error:{message}}`,
FastAPI `{detail:[...]}`, non-JSON error body, network failure, POST shape; all six decision
classes plus unknown/null degradation and per-class distinctness; language switching,
persistence, `html lang`, `aria-pressed`; advisory error branches (network, 503, 422) and
retry, each asserting that **no decision badge appears** when no decision was made.

Browser checks: five routes render with no console error and no failed request; desktop
navigation reaches all five; the five verified decisions still return from the real
`POST /rag/answer`; Hindi chrome + `html lang` + persistence; backend-unreachable state
(API calls aborted at the network layer) shows an error and not an answer; no horizontal
overflow on five routes at 390 px and 1440 px.

---

## 5. The 71 warnings

The handover's count is exactly what a plain `pytest` run reports: **71 warnings**, counted per
occurrence. Re-run with `-W default` and pytest collapses them to **11 warnings in 3 groups**,
because each location is then reported once. Neither number is wrong; they answer different
questions, and the 71 is not 71 distinct problems. Composition:

| Source | Count | Cause | Action |
|---|---|---|---|
| `starlette/testclient.py:40` | 61 | `anyio.abc.BlockingPortal` alias deprecated; starlette 0.38.6 pins an older anyio API than the installed anyio 4.15.1 | none now; resolves by upgrading FastAPI/starlette |
| `joblib/numpy_pickle.py:185` | 5 | NumPy 2.5 deprecates setting `.shape`; joblib 1.4.2 still does it | none now; resolves with a newer joblib |
| `joblib/numpy_pickle.py:188` | 5 | same | same |

**No warning originates in `app/` or `tests/`.** All three are third-party deprecations caused
by unpinned transitive dependencies: `numpy` and `anyio` were resolved to versions far newer
than the pinned September-2024 stack. This is test noise today and a reproducibility risk on a
build machine tomorrow — see blocker B5.

---

## 6. Remaining blockers, ordered

**B1 — No version control.** `C:\Users\asus\Documents\CSE276_PROJECT` is not a git
repository (`git status` fails). Vercel and Render both deploy from a repository. Required:
`git init`, add the remote, confirm `.gitignore` keeps `.env`, `.pgdata/`, `node_modules/`,
`dist/` out, and only then connect the host. Not done here because the choice of remote
(GitHub/GitLab, account, visibility) is the student's.

**B2 — The API URL is baked into the build at build time.** Confirmed by inspecting the
built bundle: `http://localhost:8000` appears in `dist/assets/index-*.js`. Deployed as-is, the
site calls the visitor's own machine. Fix: set `VITE_API_BASE_URL` in Vercel to the Render
URL **and rebuild** — Vite inlines it, so changing the variable without a redeploy fixes
nothing.

The audit proved the mechanism works end-to-end: rebuilding with
`VITE_API_BASE_URL=http://127.0.0.1:8000` and starting the backend with
`CORS_ORIGINS=http://127.0.0.1:4321` produced a production bundle with **zero console errors
and zero failed requests** and full data on all five routes. The inverse (mismatched pair)
produced a CORS failure on every request. Both directions are real evidence, not inference.

**B3 — No authentication.** Every endpoint is public, including `POST /rag/answer`, which runs
classification + embedding + retrieval + rules per call. There is no user concept, so there is
nothing to authenticate yet; the decision is whether the pilot is a public demo (protect by
rate limit and quota) or a private evaluation (protect by a shared token). Do not invent a
login to look complete. If a token is added: server-side comparison, HTTPS only, no token in
the bundle (a `VITE_*` variable is public).

**B4 — No rate limiting.** An unauthenticated, CPU-bound endpoint with no limiter is a
denial-of-service and a cost vector. 60 requests/minute/IP on `POST /rag/answer` is a sane
starting point, enforced at the platform edge (Render/Cloudflare) or with a middleware backed
by a shared store. An in-process counter is wrong behind more than one instance — note that
before implementing.

**B5 — Unpinned transitive dependencies.** `requirements.txt` pins direct dependencies;
`numpy`, `anyio`, `scipy`, `torch` resolve freely. Section 5 is the visible symptom. Before
deploying, pin the resolved set (a `constraints.txt` generated from a clean install of the
target Python version) and build once to confirm. Not done here because it cannot be verified
without a clean install, and an unverified pin is worse than none.

**B6 — Cloud database is unproven.** The code path exists; it has never run against Neon.
Required sequence, in this order, from `backend/`:
```
python -m app.db.run_migrations
python -m app.db.import_knowledge_base
```
`run_migrations` must be run against the cloud database *before* the first request, and the
deployed service must not run them at startup (concurrent instances would race). pgvector
availability makes migration 0003 choose the untested branch — set `VECTOR_STORAGE_MODE=array`
for the pilot unless that branch is deliberately tested. SQL compatibility itself is fine: the
migrations use standard PostgreSQL (`real[]`, a `DO` block, a view), not pgvector-only syntax.

**B7 — Free-tier cold starts and memory.** Render free instances sleep; the first request
after idle can take ~30–50 s, which the frontend shows as a network failure (honestly, but
badly timed). A 512 MB instance is plausible only because PyTorch is no longer installed;
`scikit-learn` + `numpy` peak well under that.

**B8 — Health check path.** `/health/ready` returns `degraded` whenever pgvector or the LLM is
absent — which is the permanent, intentional state of this pilot. Point the platform health
check at `/health` (liveness), not `/health/ready`. Do not "fix" readiness to say `ready`: its
job is to report dependency truth.

---

## 7. Recommended hosting configuration

**Frontend — Vercel (Hobby).** Root directory `frontend`. Build `npm run build`. Output `dist`.
Environment (Production): `VITE_API_BASE_URL=https://<render-service>.onrender.com` — no
trailing slash, then **redeploy**. `vercel.json` already carries the SPA rewrite and headers.
Redeploy whenever the API URL changes.

**Backend — Render (Web Service, Python).** Root directory `backend`.
Build `pip install -r requirements.txt`. Start
`uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`.
Health check path `/health`. Pin the Python version (3.12 matches the audited environment) via
`PYTHON_VERSION`.

Environment:

| Variable | Value | Why |
|---|---|---|
| `DATABASE_URL` | Neon pooled connection string | see B6 |
| `DB_SSLMODE` | `require` | managed TLS; optional if the URL already carries `sslmode` |
| `KB_REPOSITORY` | `postgres` | fail loudly in production; `json` keeps the app DB-independent |
| `VECTOR_STORE` | `postgres` | matches the tested configuration |
| `VECTOR_STORAGE_MODE` | `array` | keeps production on the tested branch |
| `EMBEDDING_PROVIDER` | `hashing` | deterministic, offline, no model download |
| `CORS_ORIGINS` | `https://<project>.vercel.app` | exact origin; `*` is refused |
| `APP_ENV` | `production` | enables the loopback-CORS warning |
| `LOG_LEVEL` | `INFO` | |
| `SUPPORTED_LANGUAGES` | `en,hi` | |
| `LLM_PROVIDER` | `ollama` (unused) | extractive generation; do not set a cloud key |

Do **not** set `CLOUD_LLM_API_KEY`: no code path uses it.

**Database — Neon (free tier).** Use the pooled endpoint (`-pooler`) for the app and the
direct endpoint for migrations, because `psycopg2` + PgBouncer transaction pooling can reject
session-level state. Run B6's two commands against the direct endpoint first.

Free-tier fit is comfortable: 9 records, 60 chunks, 384-dimension `real[]` — kilobytes.

---

## 8. Security risks

| # | Risk | Severity | State |
|---|---|---|---|
| S1 | No authentication on a compute endpoint | High (public URL) | open — B3 |
| S2 | No rate limiting / quota | High | open — B4 |
| S3 | Client-override of safety decisions | — | **closed and re-verified**: `extra="forbid"` on `RagRequest`; no route accepts a decision, status or regulatory evidence; the 422 path is covered by a frontend test |
| S4 | Regulatory-verification bypass | — | **closed** (Phase 7); `is_verified` type-checks `RegulatoryEvidence`, evidence is backend-file only, fails closed |
| S5 | Wildcard CORS with credentials | Medium | **fixed** — 3.1 |
| S6 | Oversized request bodies | Medium | **mitigated** — 3.4 (Content-Length only) |
| S7 | Stack traces / internals leaked to clients | Medium | closed: generic 500 with server-side logging only |
| S8 | Secrets in the repository | High | closed: scan clean; `.env` git-ignored; `DATABASE_URL` password is local-only |
| S9 | Public `/docs` and `/openapi.json` on the deployed API | Low | open by choice; set `docs_url=None` if the surface should be hidden |
| S10 | Prompt-injection | Low | not applicable: no LLM in the answer path; retrieval is lexical over a fixed corpus |
| S11 | Dependency drift (S5-adjacent supply chain) | Medium | open — B5 |
| S12 | Cross-lingual retrieval limits | Low | known and stated in the UI; a Hindi pest name can return crop-level records rather than one record |

---

## 9. Deliberately not done

- No deployment, no account creation, no DNS, no cloud database provisioned.
- No safety rule, threshold, decision class, prompt or knowledge record touched.
- No fabricated state for `ACTIONABLE_RECOMMENDATION` or
  `REGULATORY_VERIFICATION_REQUIRED`; they remain untested end-to-end because no record can
  produce them.
- No rate limiter and no auth implemented. B3/B4 are design decisions for the student, and a
  wrong limiter (in-process, per-instance) would be worse than a documented gap.
- No dependency pins added without a verified clean install (B5).
- `git init` not run (B1): the remote is the student's choice.

---

## 10. Gate

Phase 9 is complete as an audit. **Deployment should not start until B1–B4 are resolved and
B5/B6 are either resolved or explicitly accepted as pilot risk.** The next phase is a short
deployment execution phase: repository, then database, then backend, then frontend, verifying
each with the checks already in place rather than with a fresh manual click-through.

