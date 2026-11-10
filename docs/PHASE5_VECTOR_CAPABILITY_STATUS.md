# Phase 5 — Vector Capability Status (precise)

**Purpose:** separate three things that are easy to conflate in a summary. At the time of writing, **one is implemented, tested and executed; one is implemented, tested and executed but is *not* pgvector; one is written but has never run.**

Read this before quoting any retrieval capability of this project.

---

## 1. Summary

| # | Capability | Code written | Executed here | Tested here | May be claimed? |
|---|---|---|---|---|---|
| **A** | Array-based cosine similarity over `real[]` (`cosine_similarity()` SQL function) | Yes | **Yes** | **Yes** | **Yes** |
| **B** | pgvector **extension** enabled on a PostgreSQL server | Attempted by migration `0001` | **No** — extension absent | **No** | **No** |
| **C** | pgvector `<=>` operator + HNSW/ivfflat index (`vector(384)` cast) | Yes | **No** | **No** (path not reachable) | **No** |

The project's vector search runs entirely on **A** today. **B** and **C** are dormant.

---

## 2. State A — array-based cosine similarity: IMPLEMENTED, TESTED, EXECUTED

### 2.1 What exists

| Artifact | Detail |
|---|---|
| Column | `embeddings.embedding real[] NOT NULL`, with `CHECK (cardinality(embedding) = embedding_dim)` and `CHECK (embedding_dim = 384)` |
| SQL function | `cosine_similarity(real[], real[]) → double precision`, `IMMUTABLE STRICT PARALLEL SAFE`; returns **NULL** for mismatched or zero-length vectors rather than a misleading `0.0` |
| Query | `ORDER BY cosine_similarity(e.embedding, :q::real[]) DESC`, with `... IS NOT NULL` in the predicate |
| Storage driver | `PostgresVectorStore` (choose by reading `vector_storage_mode.mode = 'array'`) |
| Data | 60 chunks imported (9 `approved_use`, 43 `intervention`, 8 `source`) |

### 2.2 Evidence it actually ran

```
$ python -m app.db.run_migrations
Applied migrations: ['0001_enable_pgvector', '0002_knowledge_base_schema', '0003_vector_storage']

$ python -m app.db.import_knowledge_base
crops 5 | sources 8 | approved_uses 9 | interventions 43 | provenance 9
embeddings    : 60 stored (array, model hashing-lexical-v1)
                  pgvector extension is not available on this server; using exact cosine_similarity() scan over real[]

$ GET /knowledge-base/status
vector_store = {"backend": "array", "chunks": 60}

$ POST /knowledge-base/similar  {"query":"whitefly cotton spray","limit":3}
hit[0] AU-COTTON-PINK-BOLLWORM-01#1  score 0.170214
       advisory_status EDUCATIONAL_ONLY   is_actionable false
```

### 2.3 Tests that executed (not skipped)

From `backend/tests/test_phase5_postgres.py`, group B (all ran against the live local cluster):

- `TestSchemaAndMigrations::test_cosine_similarity_function_behaviour` — identical vectors → `1.0`; orthogonal → `0.0`; mismatched lengths → `NULL`.
- `TestSchemaAndMigrations::test_vector_storage_mode_is_recorded_honestly` — the recorded mode must match `pg_extension` reality.
- `TestVectorStorageInDatabase` (6 tests) — dimension integrity, ranked search, chunk-type filter, gate attachment, no index mutation on query, upsert refresh.
- `TestSchemaAndMigrations::test_rerunning_migrations_is_a_noop`.

### 2.4 Properties and limits

- **Exact**, not approximate: full scan, so recall is 1.0 by construction.
- Cost is \(O(n)\) per query — instant at 60 chunks, unsuitable at 10⁵+ without an index.
- No index exists for this path, by design (pgvector would provide one).

---

## 3. State B — pgvector extension: NOT INSTALLED, NOT VERIFIED

### 3.1 Measured evidence

```
$ ls "C:\Program Files\PostgreSQL\18\share\extension\" | Select-String vector
  (no files)

$ Test-Path "C:\Program Files\PostgreSQL\18\lib\vector.dll"
  False

$ psql -c "CREATE EXTENSION vector"
  ERROR: extension "vector" is not available
  HINT:  The extension must first be installed on the system where PostgreSQL is running.
```

`SELECT * FROM pg_available_extensions WHERE name = 'vector'` returns **no row**, which is why `/health/pgvector` reports:

```json
{"connected": false,
 "message": "pgvector extension is NOT available on this PostgreSQL server."}
```

### 3.2 Why it could not be installed here

| Route | Result |
|---|---|
| Official PostgreSQL 18 Windows installer | Does not bundle pgvector |
| Build from source | **Blocked**: no C compiler — `cl.exe` and `nmake` not found (VS shell present, C++ workload absent) |
| Docker image `pgvector/pgvector` | **Blocked**: Docker not installed |
| Managed cloud PostgreSQL | Requires an account — not created without approval |

### 3.3 Consequences, stated plainly

- `CREATE EXTENSION vector` **has never succeeded** on this project.
- `pg_extension` contains no `vector` row; `vector_storage_mode.mode = 'array'`.
- **No claim of "pgvector integration verified" is supported by this repository's evidence.**

---

## 4. State C — `<=>` + HNSW implementation: WRITTEN, NEVER EXECUTED

### 4.1 What is written

| Location | Code |
|---|---|
| `backend/migrations/0003_vector_storage.sql` | `DO` block: if the extension is present after `CREATE EXTENSION`, build `embeddings_hnsw_cosine_idx ON embeddings USING hnsw ((embedding::vector(384)) vector_cosine_ops)`; on `undefined_object`/`feature_not_supported`/`syntax_error`, fall back to `ivfflat (... ) WITH (lists = 100)`; record the outcome in `vector_storage_mode`. |
| `backend/app/vector/store.py` | Branch on `mode == "pgvector"`: score `1 - (e.embedding::vector(384) <=> (:qv)::vector)`, order by the same distance, query vector passed as a `'[..]'` literal. |

### 4.2 Why it is unexecuted

Both branches sit behind a condition that is false on this machine (`pg_available_extensions` has no `vector`). Nothing calls them. They were never run against any server, so they are **unproven code**, not a tested alternative path.

### 4.3 What could plausibly be wrong (not yet falsifiable here)

1. **Expression-index syntax on a cast.** `((embedding::vector(384)) vector_cosine_ops)` is the documented form for indexing an array column, but it has not been parsed by this PostgreSQL build.
2. **Operator resolution.** `<=>` requires the `vector` type's operator class from the extension; a version mismatch would surface only at query time.
3. **HNSW availability.** Needs pgvector ≥ 0.5; older builds fall through to `ivfflat`, which needs data to train `lists = 100` sensibly.
4. **Parameter binding.** The vector literal is passed as a text parameter cast to `vector`; psycopg2 rendering of a 384-element literal has not been exercised on this path.
5. **Schema qualification.** On managed providers the extension may live in a non-default schema: Supabase documents `extensions.vector(384)`, not `vector(384)`. My cast is unqualified, so on such a host it would fail with `type "vector" does not exist` unless `search_path` includes that schema. This is exactly the class of defect that only a real server reveals.
6. **Filtering with an ANN index.** `PostgresVectorStore.search()` applies `chunk_type = ANY(:types)` as a `WHERE` clause. With HNSW/ivfflat, pgvector filters *after* the index scan, so a filtered query can return **fewer rows than `LIMIT`** — Supabase calls this out explicitly, recommending iterative scan (`hnsw.iterative_scan`). The array path is not affected because it is an exact scan. If the pgvector path is enabled, its filtered results must be checked for under-return, and the code may need `SET LOCAL hnsw.iterative_scan = relaxed_order` or a post-filter-over-fetch strategy.

Items 5 and 6 were found by reading the providers' current pgvector documentation during this review; they are recorded here rather than fixed blind, because fixing untested code against an untested assumption is how the failing branch would get harder to diagnose.

### 4.4 How to prove it, and the acceptance criteria

```bash
# 1. Install the extension (requires superuser on the target server)
psql "<target dsn>" -c "CREATE EXTENSION vector;"

# 2. Re-run migrations; mode must flip to pgvector
python -m app.db.run_migrations
psql "<target dsn>" -c "SELECT mode, detail FROM vector_storage_mode;"

# 3. Re-import so an index exists over the same rows
python -m app.db.import_knowledge_base

# 4. Execute an actual similarity query through the extension
psql "<target dsn>" -c "SELECT chunk_ref, 1 - (embedding::vector(384) <=> \
  (SELECT embedding::vector(384) FROM embeddings LIMIT 1)) AS score \
  FROM embeddings ORDER BY embedding::vector(384) <=> \
  (SELECT embedding::vector(384) FROM embeddings LIMIT 1) LIMIT 3;"
```

State C may be marked verified **only when all four hold**:

- `pg_extension` contains `vector`, and `vector_storage_mode.mode = 'pgvector'`;
- an index named `embeddings_hnsw_cosine_idx` (or `embeddings_ivfflat_cosine_idx`) exists in `pg_indexes`;
- step 4 returns rows with a peak score of `≈1.0` for the self-match;
- `TestVectorStorageInDatabase` passes with `backend == "pgvector"`.

Until then the correct description is: **"pgvector support is implemented against an interface that has not been exercised; retrieval currently uses an exact array-based cosine scan."**

---

## 5. What this project does *not* claim

- It does **not** claim pgvector is installed, working, or benchmarked.
- It does **not** claim approximate-nearest-neighbour performance.
- It does **not** claim semantic retrieval: the default embedder is a deterministic lexical hasher (`hashing-lexical-v1`), and absolute cosine scores for correct matches are low (≈0.15–0.35). Ranking is meaningful; fixed thresholds are not.
- It does **not** claim retrieval constitutes advice: every hit carries `advisory_status: EDUCATIONAL_ONLY` and `is_actionable: false`.
