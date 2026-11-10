# Phase 4 — Supervised Classification (Module B) Implementation Report

**Status:** Implemented and tested. Awaiting review before Phase 5.
**Decisions recorded:** [DEC-011](../01_Blueprint/DECISION_LOG.md#dec-011--phase-4-supervised-classification-separate-heads-per-label-space)
**Held-out evaluation (auto-generated):** [`ml/classification/reports/PHASE4_EVALUATION_REPORT.md`](../ml/classification/reports/PHASE4_EVALUATION_REPORT.md)

---

## 1. What was built

A real, in-process supervised classifier that maps a free-text agricultural query to three independent labels:

| Dimension | Labels |
|---|---|
| **Crop** | `rice`, `wheat`, `maize`, `cotton`, `tomato`, `unsupported_crop`, `no_crop` |
| **Task** | `pest_identification`, `pest_management`, `disease_management`, `product_information`, `general_guidance`, `out_of_scope` |
| **Safety topic** | `dosage`, `phi`, `rei`, `ppe`, `toxicity`, `regulatory_approval`, `general_safety`, `no_safety_topic` |

No LLM is used. No database, no network call, no GPU: `scikit-learn` TF-IDF + logistic regression, loaded from a committed joblib artifact.

**Scope boundary (unchanged from DEC-001 / DEC-010):** the classifier emits *intent labels*. It contains no dosage, PHI, REI, PPE or registration facts, cannot approve a recommendation, and cannot change a knowledge-base record's `EDUCATIONAL_ONLY` status. This is asserted by tests, not just documented (§8).

---

## 2. Architecture decision: three separate heads, one shared feature space

Recorded as DEC-011. Options considered:

| Option | Why rejected / chosen |
|---|---|
| One joint label (7×6×8 = 336 classes) | With 211 rows, ~0.6 examples per class. Also makes "out-of-scope crop but clear safety question" unrepresentable. **Rejected.** |
| `MultiOutputClassifier` wrapping one estimator per output | Does the same thing internally, but hides per-target class sets, thresholds and confidence. We need per-dimension confidence to ask *which* dimension is unclear. **Rejected.** |
| `MultiOutputClassifier` with a shared pipeline | Would tie all three targets to one threshold policy; they need different ones. **Rejected.** |
| **Three independent heads over one shared TF-IDF matrix** | **Chosen.** Label spaces are logically independent; per-target thresholds; per-target confidence; one vocabulary, one vectorisation pass. |

The vectorizer is fitted once on training text only (unsupervised, so no label leakage) and shared; each head is a separate `LogisticRegression`.

---

## 3. Dataset

**File:** [`ml/classification/dataset/queries.csv`](../ml/classification/dataset/queries.csv) — **211 hand-labelled queries**.
**Generator / authoring source:** [`build_queries_dataset.py`](../ml/classification/dataset/build_queries_dataset.py) (deterministic, rejects duplicate texts).
**Methodology:** [`LABELING_GUIDE.md`](../ml/classification/dataset/LABELING_GUIDE.md).

| Dimension | Distribution |
|---|---|
| Language | `en` 125, `hi` 60, `hi-latn` 26 |
| Crop | `no_crop` 45, cotton 31, tomato 30, maize 29, rice 28, wheat 26, `unsupported_crop` 22 |
| Task | general_guidance 78, product_information 44, pest_management 35, disease_management 23, pest_identification 16, out_of_scope 15 |
| Safety | no_safety_topic 101, dosage 23, rei 21, phi 17, ppe 17, general_safety 12, regulatory_approval 10, toxicity 10 |

### Provenance and honesty rules applied
- Every row hand-written for this project; nothing scraped, nothing LLM-generated.
- **No row is copied from the Phase 3 knowledge base**, so classification training data and the retrieval corpus are disjoint.
- **No row asserts an agricultural fact.** Products appear only as the *subject of a question* ("what is the dose of X"); no row states a dose, PHI, REI, PPE requirement or registration status. Therefore this dataset cannot inject an invented pesticide fact into the system — it only teaches intent.
- Ambiguous rows are deliberately included (11) and flagged in a `notes` column.
- Single annotator, one author, following written rules; **no inter-annotator agreement statistic is claimed.**

### Leakage prevention
`make_splits()` uses a deterministic greedy allocation (seed 42) that balances **all three** label spaces simultaneously, then asserts (a) no normalised query text appears in two splits, (b) every label appears in every split. Single-column `train_test_split(stratify=...)` was rejected because it left `out_of_scope` and `rei` entirely absent from the test split on the first attempt — an evaluation that silently never tests a class.

Result: train 147 / dev 32 / test 32, all 21 labels present in all three splits.

---

## 4. Text preprocessing and features

- NFKC normalisation, lowercase, punctuation stripped, whitespace collapsed — applied **identically** at training and inference (prevents train/serve skew).
- Language detection is a transparent heuristic (Devanagari ratio + romanised-Hindi markers), used for reporting and for choosing the clarification language. It is **not** a trained language-ID model and is not used to route to different models.
- Features: TF-IDF word unigrams + `char_wb` 3–5 grams, `sublinear_tf=True`.

### Two Devanagari bugs found and fixed during implementation

Both were silent — the pipeline trained and "worked", just badly, on Hindi. They are worth recording because the same traps will bite Phase 5's RAG tokenisation.

1. **Preprocessing shredded Hindi.** `re.sub(r"[^\w\s]+", " ", text)` looked correct but Python's `\w` does not match Devanagari combining marks (category Mn), so `धान` → `ध न` and `कीड़ा` → `क ड`. Fixed with an explicit `\u0900-\u097F` range (regression-tested).
2. **scikit-learn dropped Hindi words entirely.** The default `token_pattern=r"(?u)\b\w\w+\b"` cannot match a Devanagari word, because its letters are separated by matras that are not `\w`. Only the char n-grams were seeing Hindi at all. Fixed with `token_pattern=r"(?u)\S+"`.

Effect of the second fix (same data, same split): crop accuracy **0.78 → 0.84**, Hindi crop queries started resolving (`गेहूं`/`मक्का`/`कपास`/`टमाटर` now 0.77–0.84 confidence), and `धान`/`कीट`/`फसल` entered the vocabulary.

---

## 5. Model selection

Selected on **training-split 5-fold cross-validation only** (never on test):

| Configuration | CV accuracy (mean of 3 targets) |
|---|---|
| word(1,2) + char_wb(3,5), lbfgs, C=2 | 0.741 |
| word(1,1) + char_wb(3,5), lbfgs, C=10 | 0.751 |
| **word(1,1) + char_wb(3,5), liblinear, C=10** | **0.756** |
| word(1,2) only (no char) | 0.677–0.710 |

Chosen: `LogisticRegression(C=10, solver="liblinear", class_weight="balanced")`.

Why liblinear over the tied multinomial `lbfgs`: on the development split its probabilities are well spread (mean max-probability **0.649**, **0/87** dimensions saturated above 0.95). A confidence gate is only meaningful if confidence is not pinned at 1.0 — the clarification logic depends on this.

Why `class_weight="balanced"`: `no_safety_topic` (101 rows) vs `regulatory_approval` (10). Without it, rare safety topics would almost never be predicted, which for a safety tool is the wrong trade even at some accuracy cost.

Why unigrams rather than bigrams: on 147 training rows, bigrams added features without measurable CV gain; unigrams + char n-grams generalise more safely.

**Threshold selection.** `min_confidence = 0.40`, `min_margin = 0.15` for all three targets, set **a priori**, sanity-checked on dev only. The margin requirement is the important one: on a 7-class text problem a single lexical cue can put 0.45 on one class and 0.40 on the runner-up, and reporting that as a definite answer would be misleading. Thresholds are **not** tuned on the test split.

---

## 6. Held-out evaluation (test split, n = 32)

Test split only; the model never saw these rows. Full report with confusion matrices: [`PHASE4_EVALUATION_REPORT.md`](../ml/classification/reports/PHASE4_EVALUATION_REPORT.md).

| Target | Accuracy | Macro P | Macro R | Macro F1 | Weighted F1 |
|---|---|---|---|---|---|
| Crop | **0.8438** | 0.8350 | 0.8405 | **0.8353** | 0.8353 |
| Task | **0.7188** | 0.5400 | 0.5051 | **0.4941** | 0.6650 |
| Safety topic | **0.8438** | 0.7000 | 0.7415 | **0.7200** | 0.8089 |

All three correct simultaneously: **16/32 (0.500)**.

### Deployed-policy behaviour (confidence gate applied)

| Metric | Value |
|---|---|
| Rows where the system asked for clarification | 9 / 32 (28%) |
| Rows answered without clarification | 23 / 32 |
| **Crop head confident → correct** | **17 / 17 (100%)** |
| All three correct *on rows it chose to answer* | 14 / 23 (60.9%) |
| Unsupported-crop rows explicitly flagged | 1 / 3 (other 2 abstained; **0 mapped to a pilot crop**) |
| Abstention rate on non-ambiguous rows | 9 / 32 (28.1%) |

The single most important number is **17/17**: every time the crop head claimed confidence, it was right. The abstention path absorbs the errors instead of shipping them.

### Per-class highlights and honest failures

- Strong: `general_guidance` F1 0.87, `product_information` 0.86, `pest_management` 0.67, `no_safety_topic` 0.83, `regulatory_approval` 1.0, `rei` 0.80.
- **`pest_identification` 0/3 (F1 0.00)** — every instance was predicted `pest_management`. "Which insect is making holes in my cotton bolls?" reads as an action request to a bag-of-words model. This is the clearest remaining weakness.
- **`out_of_scope` 0/2 (F1 0.00)** — the smallest task class (15 rows). Market-price questions were routed to `general_guidance`, both with confidence below threshold (so they abstained rather than answering).
- `ppe` recall improved materially after adding explicitly-labelled PPE phrasings; earlier runs mislabelled PPE questions as `general_safety`.

---

## 7. API

Registered additively in `backend/app/main.py`; no existing route changed.

### `POST /classification/classify`

```json
{ "query": "How many days before harvest should I stop spraying in paddy?" }
```

→ `200`

```json
{
  "query": "How many days before harvest should I stop spraying in paddy?",
  "detected_language": "en",
  "crop":     { "label": "rice", "display_label": "Rice", "confidence": 0.77,
                "margin": 0.70, "status": "confident", "alternatives": [ ... ] },
  "task":     { "label": "general_guidance", "...": "...", "status": "confident" },
  "safety_topic": { "label": "phi", "display_label": "Pre-harvest interval (PHI)",
                    "confidence": 0.87, "...": "...", "status": "confident" },
  "requires_clarification": false,
  "clarification_message": null,
  "unsupported": false,
  "out_of_scope": false,
  "scope_message": null,
  "model_version": "clf-1.0.0",
  "safety_policy": {
    "approves_pesticide_recommendation": false,
    "can_override_educational_only_gate": false,
    "advisory_gate": "UNCHANGED_EDUCATIONAL_ONLY_UNTIL_SAFETY_EVIDENCE",
    "note": "Classification identifies what the user is asking about. It is not agricultural evidence ..."
  }
}
```

`status` is one of `confident | ambiguous | unsupported | out_of_scope | not_specified | undetermined`. `safety_policy` is a typed part of the response (`Literal[False]` fields), so no consumer can be unaware that classification approves nothing.

Errors: `422` for empty/blank/over-1000-character/extra-field input (Pydantic, `extra="forbid"`); `503` when the model artifact is missing — the API fails honestly rather than inventing a prediction.

### `GET /classification/model-info`
Model version, training timestamp, taxonomy, thresholds, training metadata. For auditors and developers; not shown in the UI.

---

## 8. Safety and architecture compliance

| Requirement | How it is satisfied |
|---|---|
| Never approves a pesticide recommendation | `SafetyPolicy.approves_pesticide_recommendation: Literal[False]` on every response; test asserts it for dose/PHI/registration queries. |
| Never bypasses the Phase 3.1 `EDUCATIONAL_ONLY` restriction | `can_override_educational_only_gate: Literal[False]`; the classification package imports nothing from `app.knowledge_base` (asserted by reading the service source in a test); KB regression tests still assert all 9 records are `EDUCATIONAL_ONLY` with unpublished PHI/REI/PPE. |
| Low confidence triggers clarification or safe fallback | Per-dimension confidence + margin gate → `ambiguous` → `requires_clarification` + a ready-to-show question in the detected language. |
| Unsupported crops/topics never forced into known categories | `unsupported_crop` / `no_crop` / `out_of_scope` are explicit labels; test asserts no out-of-scope crop is ever *confidently* labelled a pilot crop. |
| Independent of PostgreSQL and Ollama | Pure scikit-learn + joblib in-process; no DB import, no LLM import, no network call. |
| Does not break existing endpoints | `/health*` and `/knowledge-base/*` unchanged and covered by regression tests. |

---

## 9. Frontend

`AdvisoryAssistant.tsx` (previously an "not yet implemented" placeholder) now offers: a question box, three example queries (EN + HI), and a **"What the assistant understood"** panel showing crop / type of question / safety point, each with a plain-language status chip (`Clear`, `Not sure`, `Outside the pilot crops`, …) and a confidence bar. A clarification box appears when the system is unsure, in the user's detected language; a scope box appears for unsupported/out-of-scope queries. A closing line states that the screen does not recommend, approve or dose any pesticide.

No raw label ids, thresholds, model names or probability vectors are shown. `apiClient` gained a `post` method (additive); `types/api.ts` gained the classification types to stay in sync with the backend schema.

---

## 10. Tests

`backend/tests/test_classification.py` — **83 tests**. Full backend suite: **132 passed, 0 failed**.

Covered: model artifact presence/loading/corrupt-artifact handling; predictions for all three dimensions; **English queries for all five crops**; **Hindi queries for all five crops**; romanised Hindi; safety-topic routing EN+HI; task routing; ambiguous queries; unsupported queries (including the hard invariant that no unsupported crop is confidently mapped to a pilot crop); low-confidence/undetermined fallback; clarification language; API validation (empty, blank, too long, wrong type, extra field); 503 path when the model is missing; existing endpoints still 200; KB `EDUCATIONAL_ONLY` and provenance intact; dataset label validity, duplicate rejection, split reproducibility, zero leakage, full label coverage; and Devanagari preprocessing regression guards.

Assertions are written as the system's real contract — *correct, or explicitly abstain* — plus measured accuracy floors (EN crops ≥5/5, HI crops ≥4/5, safety ≥8/9, task ≥4/5), so a regression fails the build instead of being absorbed.

---

## 11. Reproducing the model

```bash
# from the repository root, using the backend virtualenv
python ml/classification/dataset/build_queries_dataset.py   # regenerate queries.csv (211 rows)
python ml/classification/train_classifier.py                # trains, writes artifact + split manifest
python ml/classification/evaluate_classifier.py             # writes metrics, confusion matrices, report
```

Artifacts:
- `backend/app/classification/artifacts/classifier_v1.joblib` — runtime model (committed; ships with the backend)
- `ml/classification/artifacts/split_manifest_v1.json` — exact row ids per split
- `ml/classification/artifacts/metrics_v1.json`, `confusion_matrices_v1.json`, `training_summary_v1.json`
- `ml/classification/reports/PHASE4_EVALUATION_REPORT.md`

Retraining is deterministic given the dataset and seed 42 (asserted by a test).

---

## 12. Limitations (disclosed, not hidden)

1. **Small dataset.** 211 rows, 32 in the held-out test split. Per-class support is 1–11, so per-class precision/recall carry very wide confidence intervals. These figures characterise a pilot classifier, not a production system. This is the limitation the Phase 4 brief asked to be disclosed explicitly.
2. **Task classification is the weak dimension.** Accuracy 0.72 but macro F1 0.49, because `pest_identification` (0/3) collapses into `pest_management` and `out_of_scope` (0/2) is rarely recognised. Joint "all three correct" is only 50% as a result.
3. **Hindi is thinner than English.** 60 Devanagari rows vs 125 English. One of five Hindi crop probes abstains rather than resolving `rice`. Both Devanagari pipeline bugs are fixed, but vocabulary coverage remains the binding constraint.
4. **Abstention is high (28%).** Given the low confidence thresholds were set a priori rather than tuned, the system asks more often than strictly necessary. For a safety tool this is the safer direction, but it limits coverage.
5. **Probabilities are not formally calibrated.** No reliability-diagram-based calibration (e.g. isotonic/Platt) was applied; `class_weight="balanced"` also distorts posteriors toward rare classes. Thresholds are therefore policy settings, not calibrated probabilities.
6. **Unsupported-crop recall is 1/3 explicit.** The other two fall back to `no_crop` + clarification. Safe (never mapped to a pilot crop) but less specific — the user is asked instead of being told the crop is out of scope.
7. **Single annotator, no agreement statistic**, no adversarial/typo/voice-transcription rows, no multi-intent queries.
8. **Static artifact.** Retraining is a manual/CI step; the committed artifact can drift from the dataset if one changes without the other. `evaluate_classifier.py` refuses to evaluate if the split manifest no longer matches the dataset, which catches the most likely drift.

---

## 13. Files added / changed

| File | Change |
|---|---|
| `backend/app/classification/labels.py` | **new** — taxonomy, thresholds, display names, vagueness guard constants |
| `backend/app/classification/preprocessing.py` | **new** — normalisation (Devanagari-safe), language heuristic |
| `backend/app/classification/model.py` | **new** — feature union, multi-head model, fit/predict/save/load, status derivation |
| `backend/app/classification/service.py` | **new** — cached loader, response assembly, clarification/scope wording EN+HI |
| `backend/app/classification/schemas.py` | **new** — Pydantic request/response incl. `SafetyPolicy` |
| `backend/app/classification/__init__.py` | **new** — public exports |
| `backend/app/classification/artifacts/classifier_v1.joblib` | **new** — trained artifact |
| `backend/app/api/classification.py` | **new** — `POST /classification/classify`, `GET /classification/model-info` |
| `backend/app/main.py` | router registered (additive) |
| `backend/tests/test_classification.py` | **new** — 83 tests |
| `ml/classification/dataset/queries.csv` | **new** — 211 labelled queries |
| `ml/classification/dataset/build_queries_dataset.py` | **new** — authoring/dedup tool |
| `ml/classification/dataset/LABELING_GUIDE.md` | **new** — provenance + labelling methodology |
| `ml/classification/common.py` | **new** — dataset validation, split allocation, leakage assertions |
| `ml/classification/train_classifier.py` | **new** — training script |
| `ml/classification/evaluate_classifier.py` | **new** — evaluation + report generation |
| `ml/classification/artifacts/*.json` | **new** — split manifest, metrics, confusion matrices, training summary |
| `ml/classification/reports/PHASE4_EVALUATION_REPORT.md` | **new** — generated metrics report |
| `frontend/src/pages/AdvisoryAssistant.tsx` | placeholder replaced with classification panel |
| `frontend/src/services/classificationService.ts` | **new** |
| `frontend/src/services/apiClient.ts` | `post` added (additive) |
| `frontend/src/types/api.ts` | classification types added |
| `01_Blueprint/DECISION_LOG.md` | DEC-011 appended |

No existing module was rewritten, no working feature removed, and no Phase 3/3.1 file was modified except the decision log.

---

## 14. Evidence the application still runs

- Backend: `pytest` → **132 passed, 0 failed** (49 pre-existing + 83 new).
- Frontend: `npm run build` (`tsc -b && vite build`) → **success**, 50 modules, no type errors.
- API: `POST /classification/classify` returns the structure in §7; `GET /classification/model-info` returns `clf-1.0.0`; `/health`, `/health/ready`, `/health/db`, `/health/pgvector`, `/health/llm`, `/knowledge-base/crops` all return `200` in the same process.
