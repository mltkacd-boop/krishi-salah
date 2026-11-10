"""
Phase 4 — train the Module B classification model.

Usage (from the repository root):
    python ml/classification/train_classifier.py

Produces:
    backend/app/classification/artifacts/classifier_v1.joblib   (runtime artifact)
    ml/classification/artifacts/split_manifest_v1.json          (exact row ids per split)
    ml/classification/artifacts/training_summary_v1.json        (dataset metadata)

The model is fitted on the TRAIN split only. `dev` is used for threshold
sanity-checks and `test` is left untouched for `evaluate_classifier.py` — this
script never reports a test metric, and never reports training accuracy as if
it were generalisation performance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    ARTIFACTS_DIR,
    DATASET_PATH,
    REPO_ROOT,
    SPLIT_SEED,
    TARGET_COLUMNS,
    label_distribution,
    load_dataset,
    make_splits,
    print_split_summary,
)

from app.classification.labels import MIN_CONFIDENCE, MIN_MARGIN  # noqa: E402
from app.classification.model import MODEL_VERSION, QueryClassifier  # noqa: E402
from app.classification.preprocessing import normalize_text  # noqa: E402

RUNTIME_ARTIFACT_PATH = (
    REPO_ROOT / "backend" / "app" / "classification" / "artifacts" / "classifier_v1.joblib"
)
SPLIT_MANIFEST_PATH = ARTIFACTS_DIR / "split_manifest_v1.json"
TRAINING_SUMMARY_PATH = ARTIFACTS_DIR / "training_summary_v1.json"


def main() -> int:
    print(f"Dataset: {DATASET_PATH}")
    rows = load_dataset()
    print(f"Loaded {len(rows)} validated rows (labels checked against the taxonomy).")

    duplicate_norm = len({row.normalized for row in rows})
    if duplicate_norm != len(rows):
        raise SystemExit("Duplicate normalised texts found; refusing to train.")

    split = make_splits(rows, seed=SPLIT_SEED)
    print_split_summary(split)

    training_texts = [row.text for row in split.train]
    training_targets = {
        target: [getattr(row, target) for row in split.train] for target in TARGET_COLUMNS
    }

    print(f"\nTraining {MODEL_VERSION} on {len(split.train)} rows ...")
    classifier = QueryClassifier.train(
        texts=training_texts,
        targets=training_targets,
        model_version=MODEL_VERSION,
        training_metadata={
            "dataset_path": str(DATASET_PATH.relative_to(REPO_ROOT)),
            "dataset_rows": len(rows),
            "split_sizes": {
                "train": len(split.train),
                "dev": len(split.dev),
                "test": len(split.test),
            },
            "split_seed": SPLIT_SEED,
            "label_distribution_all": label_distribution(rows),
            "thresholds": {
                "min_confidence": MIN_CONFIDENCE,
                "min_margin": MIN_MARGIN,
            },
            "features": "TF-IDF word(1,2) + char_wb(3,5), sublinear_tf",
            "estimator": "LogisticRegression(C=1.0, class_weight='balanced', lbfgs)",
            "language_coverage": {
                language: sum(1 for row in rows if row.language == language)
                for language in ("en", "hi", "hi-latn")
            },
            "notes": (
                "Fitted on the train split only. Labels are intent signals; the model holds no "
                "agricultural facts and cannot approve a recommendation."
            ),
        },
    )

    artifact_path = classifier.save(RUNTIME_ARTIFACT_PATH)
    print(f"Artifact written: {artifact_path}")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    SPLIT_MANIFEST_PATH.write_text(
        json.dumps(
            {
                "seed": SPLIT_SEED,
                "dataset": str(DATASET_PATH.relative_to(REPO_ROOT)),
                "dataset_rows": len(rows),
                "splits": split.ids(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Split manifest written: {SPLIT_MANIFEST_PATH}")

    TRAINING_SUMMARY_PATH.write_text(
        json.dumps(classifier.training_metadata, indent=2), encoding="utf-8"
    )
    print(f"Training summary written: {TRAINING_SUMMARY_PATH}")

    # Development-split sanity check only. This is NOT a generalisation metric
    # and must never be quoted as one; the test split is evaluated separately.
    dev_predicted = classifier.predict_labels([row.text for row in split.dev])
    print("\nDevelopment-split check (sanity only, not a reported test metric):")
    for target in TARGET_COLUMNS:
        truth = [getattr(row, target) for row in split.dev]
        correct = sum(1 for a, b in zip(truth, dev_predicted[target]) if a == b)
        print(f"  {target:14s} dev accuracy {correct}/{len(truth)}")

    print("\nTraining complete. Run evaluate_classifier.py for held-out test metrics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
