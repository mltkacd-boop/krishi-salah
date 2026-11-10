# Phase 5 — PostgreSQL and pgvector Integration

**Module:** C (Knowledge Representation) and D (Retrieval support)
**Decision record:** [DEC-012](../01_Blueprint/DECISION_LOG.md)
**Status:** implemented and verified on the development machine, **with two environment blockers reported in §3** — one of which (pgvector) is worked around by a documented fallback and is still open.

---

## 1. What this phase adds

| Area | Before | After |
|---|---|---|
| Knowledge-base storage | JSON files only | JSON files **or** PostgreSQL, same interface |
| Schema enforcement | Pydantic only | Pydantic **and** database `CHECK` constraints |
| Retrieval | none | 60 embedded chunks, **exact array-based** cosine search (not pgvector — §5.5), safety gate attached to every hit |
| Migrations | `0001` (pgvector only) | `0001`–`0003`, tracked in `schema_migrations`, idempotent |
| Diagnostics | `/health/db`, `/health/pgvector` | plus `/knowledge-base/status` (live backend + storage mode) |
| Tests | 132 | **204** (72 new) |

Existing behaviour is preserved: `KB_REPOSITORY` defaults to `json`, so the application and its full test suite work with no PostgreSQL at all (Phase 3 Requirement #7 is not revoked).

---

## 2. Inspection performed before any change

| Check | Result |
|---|---|
| PostgreSQL installed | **18.4** at `C:\Program Files\PostgreSQL\18` |
| Service state | `postgresql-x64-18` running, port 5432 reachable |
| `psql` on PATH | No — must be invoked by full path |
| `pg_hba.conf` auth methods | `scram-sha-256` for `local`, `host 127.0.0.1/32`, `host ::1/128` — **no `trust` anywhere** |
| Stored credentials | no `%APPDATA%\postgresql\pgpass.conf`, no `~/.pgpass` |
| Administrator login | **fails:** `fe_sendauth: no password supplied` |
| pgvector server files | **absent:** `share/extension/vector*` → no files; `lib/vector.dll` → not found |
| C toolchain (to build pgvector) | `cl.exe` and `nmake` not found (VS 2019 shell present, C++ workload not) |
| Docker | not installed |
| Existing DB layer | `connection.py` (`get_engine`, two checks), `run_migrations.py`, 6-method `KnowledgeBaseRepository` ABC, `0001_enable_pgvector.sql` |

---

## 3. Blockers — exact statements

### Blocker 1 — no credentials for the existing cluster (**resolved without weakening auth**)

```
$ psql -U postgres -h 127.0.0.1 -w -c "SELECT 1"
psql: error: connection to server at "127.0.0.1", port 5432 failed:
             fe_sendauth: no password supplied
```

`pg_hba.conf` requires `scram-sha-256` for every entry, and no password exists anywhere on this machine. Phase 5 forbids assuming the password and forbids enabling `trust`; both were respected. This is the DEC-008 gap, now pinned to a specific cause.

**Resolution:** a *separate* project-local cluster, created with `initdb` (`scripts/setup_database.py --init-local-cluster`):

| Property | Value |
|---|---|
| Data directory | `.pgdata/` (git-ignored) |
| Port | **55432** (no conflict with the existing 5432) |
| `listen_addresses` | `127.0.0.1` only — never `0.0.0.0` |
| Authentication | `scram-sha-256` for host **and** local |
| Superuser | `pesticide_admin`, random 24-byte password, in `.pgdata/admin-credentials.json` (0600, git-ignored) |
| App role | `pesticide_app` — `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION` |
| Database | `pesticide_advisory`, owner `pesticide_app`, `PUBLIC` revoked |
| Resource tuning | `shared_buffers=128MB`, `max_connections=20`, `work_mem=8MB`, `effective_cache_size=512MB` (8 GB laptop) |
| Boot behaviour | no Windows service registered; `--start` / `--stop` are explicit |

The existing installation was not read, modified, or weakened.

### Blocker 2 — pgvector cannot be installed on this machine (**open**)

```
$ ls "C:\Program Files\PostgreSQL\18\share\extension\vector*"   →  no files
$ ls "C:\Program Files\PostgreSQL\18\lib\vector.dll"            →  not found
$ CREATE EXTENSION vector
  ERROR: extension "vector" is not available
  HINT:  The extension must first be installed on the system where PostgreSQL is running.
```

The stock PostgreSQL 18 Windows build does not ship pgvector, and it cannot be compiled here because no C compiler is installed. Therefore **`CREATE EXTENSION vector` cannot succeed on this machine today**, and the Phase 5 completion criterion "pgvector extension works" is **not met** — it is an environment limitation, not a code defect.

Three viable routes, none of which this phase took without approval:

1. **Install the Visual Studio C++ build tools**, then `nmake /F Makefile.win` + `nmake install` against `C:\Program Files\PostgreSQL\18` from a pgvector source checkout. Free; ~1–2 GB of tooling; no account.
2. **Use a managed PostgreSQL with pgvector** (e.g. a free tier). Requires an external account and, in some cases, payment — explicitly out of scope without approval.
3. **Stay on the current fallback** (exact cosine scan), which is correct but \(O(n)\); at 60 chunks it is instant.

**What was done instead of pretending:** vector storage is isolated in migration `0003` and works without the extension (§5.5). `/health/pgvector` continues to report `connected: false` truthfully; `/knowledge-base/status` reports `"backend": "array"`. The `pgvector` path (`<=>` operator + HNSW index) is implemented and will activate on the next migration run once the extension exists — but it is **unverified on this machine**, and that is stated in §9.

---

## 4. Schema

Migrations apply in filename order, are tracked in `schema_migrations`, and are safe to re-run (`0001`–`0003`; a second run returns `No new migrations to apply`).

| Table | Purpose | Key constraints |
|---|---|---|
| `crops` | 5 pilot crops | PK `crop_id` |
| `sources` | 8 authoritative sources | `url` must be http(s); `reliability_tier` closed set; missing `publication_date` requires a note |
| `approved_uses` | 9 pest-management records | `verification_status` ∈ {`VERIFIED_SOURCE_RECOMMENDATION`, `UNVERIFIED_DRAFT`}; `verification_note` must exceed 20 chars; FKs to crops/sources |
| `approved_use_safety_restrictions` | record-level PHI/REI/PPE | status ∈ {`PUBLISHED`, `NOT_PUBLISHED_IN_SOURCE`}; `PUBLISHED` ⇒ value; `NOT_PUBLISHED_IN_SOURCE` ⇒ note |
| `interventions` | 43 measures | `control_type` closed set; ordinal > 0; per-product safety override is all-or-nothing |
| `provenance_records` | DEC-010 audit trail | `document_sha256` matches `^[0-9a-f]{64}$`; bytes > 0; excerpt > 20 chars |
| `embeddings` | 60 chunks | `embedding_dim = 384`; array length must equal dim; unique `(chunk_type, chunk_ref, embedding_model)` |
| `vector_storage_mode` | which vector path is live | single row; mode ∈ {`pgvector`, `array`} |
| `approved_use_advisory_status` (**view**) | the Phase 3.1 gate in SQL | derived, never stored |

### 4.1 Source verification vs regulatory approval

Preserved in three places, independently:

- the `verification_status` type has no value that could mean "CIB&RC registered";
- `provenance_records.document_sha256` is documented as proving **integrity**, not authenticity or approval;
- the `sources` table backs only the "we transcribed this correctly from a named, fetchable page" claim.

### 4.2 Why `advisory_status` is a view

A stored column could drift from the safety fields and let an incomplete record look actionable. The view recomputes the gate from the data on every read. `PostgresKnowledgeBaseRepository.assert_advisory_status_consistency()` compares it with the Pydantic rule for every record, and the importer **fails** if they disagree — which is what happened to be true for all 9 records:

```
advisory: all 9 → EDUCATIONAL_ONLY
consistency mismatches: []
```

---

## 5. Implementation

### 5.1 Provisioning — `scripts/setup_database.py`

`--status`, `--init-local-cluster`, `--existing`, `--start`, `--stop`, `--verify`. `--existing` reads the administrator password with `getpass` (never echoed, never written, never on a command line); `--init-local-cluster` needs no existing password at all. Both end by writing `DATABASE_URL` into `backend/.env` (git-ignored) and by verifying that `pesticide_app` can log in **without** elevated attributes:

```
OK   logged in as pesticide_app to pesticide_advisory without elevated privileges
```

### 5.2 Migrations — `backend/app/db/run_migrations.py`

Rewritten to execute each file through a raw `psycopg2` cursor inside one transaction. Two measured reasons: `text()` turns `%` in a `RAISE NOTICE` into a driver placeholder, and `exec_driver_sql()` fails with `TypeError: sqlalchemy.cyextension.immutabledict.immutabledict is not a sequence`. Running the reviewed SQL byte-for-byte avoids both and keeps a failed migration rolled back and unrecorded.

### 5.3 Import — `backend/app/db/import_knowledge_base.py`

Validates every record with the Phase 3 models **before** any SQL; writes in a single transaction; upserts (re-running is a no-op); replaces interventions per record so a removed measure disappears; imports the provenance manifest; then verifies its own output — row counts must match the source files and the advisory view must agree with the rule engine. `--dry-run` validates without writing.

```
crops 5 | sources 8 | approved_uses 9 | interventions 43 | provenance 9
database rows : {'crops': 5, 'sources': 8, 'approved_uses': 9,
                 'interventions': 43, 'provenance_records': 9}
embeddings    : 60 stored (array, model hashing-lexical-v1)
Import OK.
```

### 5.4 Repository — `backend/app/knowledge_base/postgres_repository.py`

Implements all six `KnowledgeBaseRepository` methods; rows are mapped back into the **existing** Pydantic models, so there is still exactly one definition of the anti-fabrication rules. Four grouped queries, no N+1. Read-only by design: writes only happen through the importer.

Selection (`factory.py`), by environment variable only:

| `KB_REPOSITORY` | Behaviour |
|---|---|
| `json` (default) | JSON files; no database needed |
| `postgres` | PostgreSQL only; **raises** if unreachable — never silently serves JSON |
| `auto` | PostgreSQL if reachable, else JSON, with the reason exposed by `/knowledge-base/status` |

### 5.5 Vector storage — `backend/app/vector/`

- `embedding.py` — `HashingEmbeddingProvider` (default), `SentenceTransformerProvider` (optional), `get_embedding_provider()`.
- `chunking.py` — deterministic chunk construction: one `approved_use` chunk, one `intervention` chunk per measure, one `source` chunk per source.
- `store.py` — `PostgresVectorStore` and `InMemoryVectorStore` behind one interface.

Storage path is **read from the database**, not assumed:

| `vector_storage_mode` | Search implementation |
|---|---|
| `pgvector` | `1 - (embedding::vector(384) <=> :q)`, HNSW/ivfflat index |
| `array` | `cosine_similarity(embedding, :q::real[])`, exact scan |

Measured on this machine: `array`, `pgvector extension is not available on this server; using exact cosine_similarity() scan over real[]`.

> **Precision required when describing retrieval.** Only the `array` row above has executed. The `pgvector` row is written code whose branch has never been reached, because the extension is absent. The full three-way distinction — what is implemented+tested, what is merely written, and what has never run — is in [PHASE5_VECTOR_CAPABILITY_STATUS.md](PHASE5_VECTOR_CAPABILITY_STATUS.md). Do not describe this project as having "verified pgvector support".

**Honest note on the embedder.** `hashing-lexical-v1` is a deterministic lexical hasher, not a semantic model. It has no synonymy and no cross-lingual ability, and absolute cosine scores are low even for correct matches (≈0.15–0.35) — use **ranking**, not a fixed threshold. A real model is a one-variable swap (`EMBEDDING_PROVIDER`), after which the importer must re-run and `embedding_model` makes a mixed index detectable.

### 5.6 API — additive only

| Endpoint | Purpose |
|---|---|
| `POST /knowledge-base/similar` | cosine search; 503 when the store is unavailable (an empty list would falsely mean "nothing matched") |
| `GET /knowledge-base/status` | live repository backend, record counts, vector backend + storage detail |

Every hit carries `advisory_status` (joined from the view) and `is_actionable`, plus a fixed `notice`. A retrieved dosage therefore cannot arrive without its gate.

---

## 6. Test evidence

```
$ python -m pytest -q          # post-review re-run, live local cluster running
204 passed, 71 warnings in 25.45s
```

72 new tests in `backend/tests/test_phase5_postgres.py`, in three groups:

- **No database required (always runs):** migration SQL contract (required tables; `verification_status` value list contains no approval-implying value; no stored `advisory_status` column; embeddings table does not require pgvector; `0001` is non-fatal), chunking coverage/uniqueness/determinism, embedding determinism/L2-normalisation/Devanagari handling/related-vs-unrelated ranking, in-memory store ranking/filters/idempotency, request validation, 503 behaviour, and repository-selection rules (including "postgres mode must not silently fall back").
- **Requires a live migrated database (skips with an explicit reason otherwise):** migration bookkeeping and idempotency; recorded storage mode **must match reality**; `cosine_similarity` behaviour including `NULL` for mismatched dimensions; import counts and idempotency and dry-run; provenance hashes; **byte-for-byte parity with the JSON repository**; ordering determinism; safety-gate consistency between SQL view and Python rule; and four tests that the **database itself rejects** a PUBLISHED field without a value, a silent gap, an approval-implying status, and a dangling crop reference.
- **Regression:** JSON stays the default; `/knowledge-base/crops|approved-uses` unchanged; `/classification/classify` still returns `approves_pesticide_recommendation: false` and `can_override_educational_only_gate: false`; `/health`, `/health/db` unchanged.

### 6.1 Live server, `KB_REPOSITORY=postgres VECTOR_STORE=postgres`

```
GET /health/db                 {"connected":true,"message":"Database connection successful."}
GET /health/pgvector           {"connected":false,"message":"pgvector extension is NOT available on this PostgreSQL server."}
GET /knowledge-base/status     repository_backend=postgres, records={crops:5,sources:8,approved_uses:9},
                               vector_store={backend:"array", chunks:60}
GET /knowledge-base/crops      cotton,maize,rice,tomato,wheat
POST /knowledge-base/similar   hit: AU-COTTON-PINK-BOLLWORM-01#1, score 0.170214,
                               advisory_status=EDUCATIONAL_ONLY, is_actionable=false
POST /classification/classify  200, crop=cotton conf 0.8767
```

### 6.2 Frontend

```
$ npm run build                # post-review re-run
✓ 50 modules transformed.
dist/index.html                 0.48 kB │ gzip:  0.31 kB
dist/assets/index-CyRh93HD.css 14.45 kB │ gzip:  3.39 kB
dist/assets/index-CwmjyUP4.js 186.45 kB │ gzip: 60.04 kB
✓ built in 8.43s
```

---

## 7. Cleanup performed before Phase 5 (items 1–5)

**1–3. `.gitignore`.** The previous edit had genuinely not applied. The file was rewritten in full and its rules then verified **semantically** in a throwaway git repository — the project directory is not itself a git repository, so `git check-ignore` cannot be run in place. 26 paths were probed; the results below are from `git check-ignore -v --no-index`, which reports the *actual rule* that decided each case:

| Path probed | Result | Rule that decided it |
|---|---|---|
| `.env` | ignored | `*.env` |
| `backend/.env`, `frontend/.env` | ignored | `backend/.env`, `frontend/.env` |
| `backend/.env.local` | ignored | `.env.*` |
| `backend/.env.example`, `frontend/.env.example` | **trackable** | `!*.env.example` |
| `backend/.venv/pyvenv.cfg` | ignored | `.venv/` |
| `backend/app/__pycache__/*.pyc` | ignored | `**/__pycache__/` |
| `ml/classification/__pycache__/*.pyc` | ignored | `ml/classification/**/__pycache__/` (previously **unguarded**) |
| `frontend/dist/index.html` | ignored | `dist/` |
| `frontend/node_modules/...`, `node_modules/...` | ignored | `node_modules/` |
| `ml/trained_models/*.joblib` | ignored | `ml/trained_models/*.joblib` |
| `backend/app/classification/artifacts/classifier_v1.joblib` | **trackable** | `!backend/app/classification/artifacts/*.joblib` |
| `backend/app/vector/store.py`, `backend/migrations/0003_vector_storage.sql`, `docs/PHASE5_DATABASE_REPORT.md` | **trackable** | (no rule — source must be committed) |
| `scratch/*.tmp` | ignored | `scratch/` |
| `backend/.pytest_cache/...` | ignored | `.pytest_cache/` |
| `app.log` | ignored | `*.log` |
| `secrets/prod.yaml` | ignored | `secrets/` |
| `certs/server.pem` | ignored | `*.pem` |
| `.DS_Store` | ignored | `.DS_Store` |
| `.pgdata/PG_VERSION`, `.pgdata/admin-credentials.json` | ignored | `.pgdata/` |
| `pgdata/x` | ignored | `pgdata/` |

**4. Secret scan.** `scripts/audit_secrets.py` scans every non-ignored text file (**118–119 depending on the run**) with 10 rules: password-bearing connection URLs, AWS access-key IDs, private-key blocks, OpenAI/Anthropic/Google/GitHub/Slack tokens, JWTs, and `KEY=value` assignments whose value looks like a secret. Two bugs in my own first version were found and fixed during this review:

- the allow-list skipped any line containing `#`, `example`, `test_` or `assert`, which would have hidden a real secret in a comment or a fixture — it is now restricted to code that *obtains* a secret at runtime (`os.getenv`, `settings.`, `getpass`, `secrets.token_urlsafe`);
- when replacing the leading `\b` with a lookbehind I silently dropped the `(?i)` flag, so `DB_PASSWORD=…` stopped matching. Caught by the positive-control suite, not by the clean run.

The scanner is validated by **negative** as well as positive controls: 8 known-bad samples must fire (including a secret inside a comment and inside a `test_`-prefixed fixture), and the two **real** local credentials (app password from `backend/.env`, superuser password from `.pgdata/admin-credentials.json`) must appear in **zero** committable files. Current result:

```
Scanned 118 text files under CSE276_PROJECT/ (10 rules).
Skipped (git-ignored secret files, expected to hold local credentials):
  - backend/.env
  - frontend/.env
RESULT: no secrets in committable files.        (exit 0)

positive controls: 8/8 fired
negative controls: 119 committable files checked, leaks = 0
```

**One genuine finding, now fixed.** The tightened scanner flagged a literal credential in a committed document: `02_Phase2_Setup/PHASE2_IMPLEMENTATION_PLAN.md` lines 116 and 169 contained a `docker run` example with `POSTGRES_PASSWORD=` set to a literal development password (the value is deliberately **not** reproduced here — quoting it would re-introduce the very finding). That is a hardcoded password in version control — placeholder-strength and never used on this machine (Docker is not installed), but it violates the project's own rule and would fail a CI gate. Both occurrences were replaced with a shell-indirection that fails fast if the variable is unset:

```bash
docker run --name pesticide-db -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?export this in your shell; never commit it}" \
  -e POSTGRES_DB=pesticide_advisory -p 5432:5432 -d pgvector/pgvector:pg15
```

No other file was edited for this. `backend/.env` (git-ignored) holds the real generated password **by design** and is excluded from the scan as an expected local secret file; `backend/.env.example` contains only `CHANGE_ME_PASSWORD`; `CLOUD_LLM_API_KEY` is empty. The real password is not reproduced in this report or any other file — that is asserted mechanically, not by inspection.

**5. `.gitignore` contents** are reproduced verbatim in `§7.1` below.

### 7.1 Exact `.gitignore` (98 lines)

```gitignore
# =============================================================================
# Secrets and environment files — NEVER commit these
# =============================================================================
.env
.env.*
!.env.example
*.env
!*.env.example
backend/.env
frontend/.env
.secrets
secrets/
*.pem
*.key
*.pfx
*.p12
id_rsa
id_rsa.*
credentials.json
service-account*.json
*.kdbx

# =============================================================================
# Python / backend
# =============================================================================
backend/.venv/
.venv/
venv/
**/__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# =============================================================================
# Node / frontend
# =============================================================================
frontend/node_modules/
frontend/dist/
frontend/.vite/
node_modules/
dist/
*.tsbuildinfo

# =============================================================================
# Machine-learning artifacts
# =============================================================================
# NOTE: the runtime classifier artifact IS intentionally committed:
#   backend/app/classification/artifacts/classifier_v1.joblib
# The API loads it at startup, it is small (a few hundred KB), and shipping it
# keeps the service runnable without a training step. Do not ignore that path.
#
# Regenerable/heavy training outputs stay out of version control.
ml/classification/**/__pycache__/
ml/trained_models/*.joblib
ml/trained_models/*.pkl
ml/classification/artifacts/*.tmp
!backend/app/classification/artifacts/*.joblib

# =============================================================================
# Temporary / scratch files
# =============================================================================
*.tmp
*.temp
*.bak
*.orig
*.rej
*.swp
*~
*.log
logs/
tmp/
temp/
scratch/

# Project-local PostgreSQL cluster created by scripts/setup_database.py
# (contains a database cluster and its generated credentials — never commit)
.pgdata/
pgdata/

# Local audit/build scratch that must never be treated as a deliverable
/dump.rdb
*.sql.gz
.pgpass

# =============================================================================
# OS / editor
# =============================================================================
.DS_Store
Thumbs.db
desktop.ini
.vscode/
.idea/
*.iml
```

---

## 8. Files added or changed

**Added**
- `backend/migrations/0002_knowledge_base_schema.sql`
- `backend/migrations/0003_vector_storage.sql`
- `backend/app/db/import_knowledge_base.py`
- `backend/app/knowledge_base/postgres_repository.py`
- `backend/app/knowledge_base/factory.py`
- `backend/app/vector/{__init__,embedding,chunking,store}.py`
- `backend/app/api/retrieval.py`
- `backend/app/schemas/retrieval.py`
- `backend/tests/test_phase5_postgres.py`
- `scripts/setup_database.py`
- `scripts/audit_secrets.py`
- `docs/PHASE5_DATABASE_REPORT.md`

**Changed**
- `backend/migrations/0001_enable_pgvector.sql` — non-fatal attempt instead of a bare `CREATE EXTENSION`
- `backend/app/db/run_migrations.py` — raw DBAPI cursor
- `backend/app/db/connection.py` — bounded pool, `application_name`, `dispose_engine()`
- `backend/app/knowledge_base/__init__.py` — exports the factory
- `backend/app/main.py` — adds the retrieval router (additive)
- `backend/.env.example` — documents `KB_REPOSITORY`, `VECTOR_STORE`, `EMBEDDING_PROVIDER`
- `.gitignore`, `01_Blueprint/DECISION_LOG.md` (DEC-012)

**Not changed:** all Phase 1–4 API routes, models, classifier and frontend.

---

## 9. Limitations (disclosed, not hidden)

1. **pgvector is unverified here.** The `<=>` + HNSW path is implemented and covered by code review and by the mode-consistency test, but it has never executed on this machine. It activates on the next `python -m app.db.run_migrations` once the extension exists.
2. **Exact scan scales linearly.** Fine at 60 chunks; a full production knowledge base would need pgvector indexes or another ANN store.
3. **The embedder is lexical.** No synonymy ("bollworm" ≠ "larva"), no cross-lingual matching, low absolute scores. Ranking is meaningful; absolute thresholds are not.
4. **The local cluster does not auto-start.** After a reboot, `python scripts/setup_database.py --start` is required; until then `/health/db` reports the failure honestly and `KB_REPOSITORY=json` keeps the app working.
5. **No backup, replication or least-privilege-per-table policy.** Single-user development database.
6. **`KB_REPOSITORY` is process-wide and read once.** Changing it requires a restart.
7. **Ordering difference:** the Postgres repository orders by primary key; the JSON repository preserves file order. Content is identical (a test asserts byte-for-byte parity of model dumps).
8. **The superuser password for the local cluster is on disk** (`.pgdata/admin-credentials.json`, 0600, git-ignored). It exists because `CREATE EXTENSION` needs superuser. Anyone with the file controls the local cluster; it must not be copied off the machine.

---

## 10. Completion criteria

| Criterion | Status |
|---|---|
| Database connection succeeds | **Met** — `pesticide_app` logs in without elevated privileges |
| pgvector extension works | **Not met** — the extension is not installed on this server and `CREATE EXTENSION vector` has never succeeded here. The `<=>`/HNSW code exists but has never executed. See §5.5 and [PHASE5_VECTOR_CAPABILITY_STATUS.md](PHASE5_VECTOR_CAPABILITY_STATUS.md). Not claimed anywhere in this repository. |
| Vector similarity search works | **Met for the array path only** — exact `cosine_similarity()` scan over `real[]`, executed and tested (60 chunks). This is not pgvector. |
| Knowledge-base records import correctly | **Met** — 5/8/9/43/9 rows, verified against source files |
| Existing API endpoints continue working | **Met** — regression tests plus live-server checks |
| All tests pass | **Met** — see §6 for the exact count from the post-review run |
| Frontend production build succeeds | **Met** |
| Database credentials are not exposed | **Met after one fix** — a hardcoded `POSTGRES_PASSWORD` literal was found in a Phase 2 planning document and removed (§7; value not reproduced). Both real local credentials are asserted absent from all 119 committable files. |
| Documentation and DEC-012 updated | **Met** |

Phase 6 has not been started.

---

## 11. Recommended secure cloud PostgreSQL for extension verification (no account created)

The local cluster cannot satisfy the pgvector criterion, and inventing a workaround would be worse than reporting the gap. The cheapest honest path is a managed development database. **Nothing was created, no credentials were obtained, and no cost was incurred** — this is a recommendation only.

### 11.1 Primary recommendation — Neon

Chosen because it removes both blockers at once: pgvector is available **on every plan with no add-on or paid tier required** (Neon's pgvector documentation, updated 2026-09-26), and it is serverless, so an 8 GB laptop pays no RAM cost for keeping a second PostgreSQL resident.

- Enable with the same statement the migration already issues: `CREATE EXTENSION IF NOT EXISTS vector;` — so **no application code changes** are needed, only `DATABASE_URL`.
- HNSW and IVFFlat are both supported, which is what the written-but-unexecuted branch in `store.py` and migration `0003` expects.
- Standard libpq connection string, so `KB_REPOSITORY=postgres` and the existing SQLAlchemy engine work unchanged.
- Branching is useful for the next steps: verify the extension on a branch, keep the demo branch stable.

### 11.2 Alternative — Supabase

Also a documented pgvector host with a dashboard-based extension toggle. Two caveats specific to this codebase: the vector type is documented as `extensions.vector(384)` (schema-qualified), and filtered ANN queries can under-return — both are recorded as risks 5 and 6 in [PHASE5_VECTOR_CAPABILITY_STATUS.md](PHASE5_VECTOR_CAPABILITY_STATUS.md).

### 11.3 Not verified in this session

Amazon RDS/Aurora, Azure Database for PostgreSQL Flexible Server and Google Cloud SQL also offer pgvector, but I did not check their current plans or regional availability, so no claim is made about them here.

### 11.4 Hardening required before any cloud use

1. `DATABASE_URL` must carry `?sslmode=require` (the local cluster is loopback, so TLS was not exercised).
2. Keep `KB_REPOSITORY=json` as the default in the committed `.env.example`; the cloud DSN lives only in an uncommitted `.env` or the platform's secret store.
3. Create the application role with the same least-privilege attributes used locally (`NOSUPERUSER NOCREATEDB NOCREATEROLE`); run `CREATE EXTENSION` **once** as an administrator, not from the app role.
4. Re-run `python -m app.db.run_migrations` and confirm `vector_storage_mode.mode` flips to `pgvector` before claiming anything.
5. Re-import so the index is built over the same 60 chunks.

### 11.5 Acceptance test that would let me close the criterion

Exactly §4.4 of the capability report: `pg_extension` contains `vector`; `vector_storage_mode.mode = 'pgvector'`; an HNSW/ivfflat index appears in `pg_indexes`; a real `<=>` query returns a self-match near `1.0`; and `TestVectorStorageInDatabase` passes with `backend == "pgvector"`. Until all five hold, this project's position remains: **array-based exact cosine search is implemented and tested; pgvector support is written but unverified.**
