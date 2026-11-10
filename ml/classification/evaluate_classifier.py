"""
Phase 4 — evaluate the trained Module B classifier on the held-out test split.

Usage (from the repository root):
    python ml/classification/evaluate_classifier.py

Reads the artifact produced by `train_classifier.py` and the split manifest it
wrote, so evaluation uses **exactly** the rows the model never saw. The split
manifest is re-verified against the dataset, and leakage is re-asserted here —
evaluation does not trust that training got it right.

Reports two things separately, because they measure different things:
1. **Classifier quality** — raw argmax predictions, so precision/recall/F1
   reflect the model itself.
2. **Deployed policy behaviour** — what the API would actually do, including
   abstentions ("ambiguous") from the confidence gate. A system that abstains
   often can be *more* trustworthy than one with slightly higher raw accuracy
   that answers wrongly, so fusing the two into one number would hide the
   trade-off the safety design is built on.

Outputs:
    ml/classification/artifacts/metrics_v1.json
    ml/classification/artifacts/confusion_matrices_v1.json
    ml/classification/reports/PHASE4_EVALUATION_REPORT.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    ARTIFACTS_DIR,
    REPORTS_DIR,
    TARGET_COLUMNS,
    VALID_LABELS,
    assert_no_leakage,
    load_dataset,
    make_splits,
)

from app.classification.labels import CROP_DEPENDENT_TASKS, MIN_CONFIDENCE, MIN_MARGIN  # noqa: E402
from app.classification.model import QueryClassifier  # noqa: E402

from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

RUNTIME_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "app" / "classification" / "artifacts" / "classifier_v1.joblib"
)
SPLIT_MANIFEST_PATH = ARTIFACTS_DIR / "split_manifest_v1.json"
METRICS_PATH = ARTIFACTS_DIR / "metrics_v1.json"
CONFUSION_PATH = ARTIFACTS_DIR / "confusion_matrices_v1.json"
REPORT_PATH = REPORTS_DIR / "PHASE4_EVALUATION_REPORT.md"


def _per_class_table(y_true, y_pred, labels) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=list(labels), zero_division=0
    )
    return {
        label: {
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "f1": round(float(f), 4),
            "support": int(s),
        }
        for label, p, r, f, s in zip(labels, precision, recall, f1, support)
    }


def _macro_weighted(y_true, y_pred) -> dict:
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_precision": round(float(weighted_p), 4),
        "weighted_recall": round(float(weighted_r), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "n": len(y_true),
    }


def main() -> int:
    rows = load_dataset()
    split = make_splits(rows, seed=json.loads(SPLIT_MANIFEST_PATH.read_text())["seed"])
    assert_no_leakage(split)

    manifest = json.loads(SPLIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_test_ids = manifest["splits"]["test"]
    actual_test_ids = [row.row_id for row in split.test]
    if sorted(expected_test_ids) != sorted(actual_test_ids):
        raise SystemExit(
            "Split manifest does not match the dataset-derived split. The dataset changed after "
            "training; retrain before evaluating."
        )

    classifier = QueryClassifier.load(RUNTIME_ARTIFACT_PATH)
    print(f"Loaded {classifier.model_version} (trained {classifier.trained_at})")

    test_texts = [row.text for row in split.test]
    truth = {target: [getattr(row, target) for row in split.test] for target in TARGET_COLUMNS}
    predicted = classifier.predict_labels(test_texts)

    metrics: dict = {
        "model_version": classifier.model_version,
        "trained_at": classifier.trained_at,
        "evaluation_split": "test",
        "test_rows": len(split.test),
        "seed": manifest["seed"],
        "thresholds": {"min_confidence": MIN_CONFIDENCE, "min_margin": MIN_MARGIN},
        "targets": {},
    }
    confusion: dict = {}

    for target in TARGET_COLUMNS:
        y_true = truth[target]
        y_pred = [str(p) for p in predicted[target]]
        labels = list(VALID_LABELS[target])
        metrics["targets"][target] = {
            **_macro_weighted(y_true, y_pred),
            "per_class": _per_class_table(y_true, y_pred, labels),
        }
        matrix = confusion_matrix(y_true, y_pred, labels=labels)
        confusion[target] = {
            "labels": labels,
            "matrix": matrix.tolist(),
        }
        print(
            f"{target:14s} accuracy={metrics['targets'][target]['accuracy']:.4f} "
            f"macro_f1={metrics['targets'][target]['macro_f1']:.4f}"
        )

    exact_all_three = sum(
        1
        for i in range(len(split.test))
        if all(truth[t][i] == str(predicted[t][i]) for t in TARGET_COLUMNS)
    )
    metrics["all_three_correct"] = {
        "correct": exact_all_three,
        "total": len(split.test),
        "accuracy": round(exact_all_three / len(split.test), 4),
    }

    # --- Deployed policy behaviour (confidence gate + clarification) --------
    from app.classification.service import classify_query

    policy = {
        "requires_clarification": 0,
        "answered_without_clarification": 0,
        "confident_crop_correct": 0,
        "confident_crop_total": 0,
        "unsupported_rows": 0,
        "unsupported_flagged": 0,
        "status_counts": {target: Counter() for target in TARGET_COLUMNS},
        "unnecessary_clarification_on_clear_rows": 0,
        "answered_rows_all_three_correct": 0,
        "answered_per_target_correct": {target: 0 for target in TARGET_COLUMNS},
    }
    clear_rows = 0

    for row in split.test:
        response = classify_query(row.text)
        answered = not response.requires_clarification
        if answered:
            policy["answered_without_clarification"] += 1
            per_target_ok = []
            for target in TARGET_COLUMNS:
                per_target_ok.append(getattr(response, target).label == getattr(row, target))
                if per_target_ok[-1]:
                    policy["answered_per_target_correct"][target] += 1
            if all(per_target_ok):
                policy["answered_rows_all_three_correct"] += 1
        else:
            policy["requires_clarification"] += 1

        for target in TARGET_COLUMNS:
            policy["status_counts"][target][getattr(response, target).status] += 1

        if response.crop.status == "confident":
            policy["confident_crop_total"] += 1
            if response.crop.label == row.crop:
                policy["confident_crop_correct"] += 1

        if row.crop == "unsupported_crop":
            policy["unsupported_rows"] += 1
            if response.unsupported:
                policy["unsupported_flagged"] += 1

        # A "clear" row is one that is not deliberately ambiguous in the dataset.
        if not row.notes.startswith("ambiguous"):
            clear_rows += 1
            if response.requires_clarification:
                policy["unnecessary_clarification_on_clear_rows"] += 1

    answered = policy["answered_without_clarification"]
    policy["answered_all_three_accuracy"] = (
        round(policy["answered_rows_all_three_correct"] / answered, 4) if answered else 0.0
    )
    policy["answered_per_target_accuracy"] = {
        target: round(policy["answered_per_target_correct"][target] / answered, 4)
        if answered
        else 0.0
        for target in TARGET_COLUMNS
    }

    policy["status_counts"] = {
        target: dict(counts) for target, counts in policy["status_counts"].items()
    }
    policy["clear_rows"] = clear_rows
    policy["abstention_rate_on_clear_rows"] = round(
        policy["unnecessary_clarification_on_clear_rows"] / clear_rows, 4
    ) if clear_rows else 0.0
    metrics["policy_behaviour"] = policy

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    CONFUSION_PATH.write_text(json.dumps(confusion, indent=2), encoding="utf-8")
    print(f"\nMetrics written: {METRICS_PATH}")
    print(f"Confusion matrices written: {CONFUSION_PATH}")

    _write_markdown_report(metrics, confusion)
    print(f"Report written: {REPORT_PATH}")
    return 0


def _write_markdown_report(metrics: dict, confusion: dict) -> None:
    lines: list[str] = []
    lines.append("# Phase 4 — Held-out Evaluation Report (Module B)")
    lines.append("")
    lines.append(
        f"Generated by `ml/classification/evaluate_classifier.py` for model "
        f"`{metrics['model_version']}` (trained {metrics['trained_at']})."
    )
    lines.append("")
    lines.append(
        f"Held-out **test split only** ({metrics['test_rows']} rows the model never saw), "
        f"split seed {metrics['seed']}. Training accuracy is not reported here and must not be "
        f"quoted as a generalisation metric."
    )
    lines.append("")
    lines.append("## Aggregate metrics per target")
    lines.append("")
    lines.append("| Target | Accuracy | Macro P | Macro R | Macro F1 | Weighted F1 | n |")
    lines.append("|---|---|---|---|---|---|---|")
    for target, m in metrics["targets"].items():
        lines.append(
            f"| `{target}` | {m['accuracy']:.4f} | {m['macro_precision']:.4f} | "
            f"{m['macro_recall']:.4f} | {m['macro_f1']:.4f} | {m['weighted_f1']:.4f} | {m['n']} |"
        )
    lines.append("")
    a = metrics["all_three_correct"]
    lines.append(
        f"**All three targets correct simultaneously:** {a['correct']}/{a['total']} "
        f"({a['accuracy']:.4f})."
    )
    lines.append("")

    for target, m in metrics["targets"].items():
        lines.append(f"## Per-class metrics — `{target}`")
        lines.append("")
        lines.append("| Class | Precision | Recall | F1 | Support |")
        lines.append("|---|---|---|---|---|")
        for label, row in m["per_class"].items():
            lines.append(
                f"| `{label}` | {row['precision']:.4f} | {row['recall']:.4f} | "
                f"{row['f1']:.4f} | {row['support']} |"
            )
        lines.append("")
        lines.append(f"Confusion matrix — `{target}` (rows = truth, columns = predicted):")
        lines.append("")
        labels = confusion[target]["labels"]
        lines.append("| truth \\ pred | " + " | ".join(f"`{l}`" for l in labels) + " |")
        lines.append("|---" * (len(labels) + 1) + "|")
        for label, matrix_row in zip(labels, confusion[target]["matrix"]):
            lines.append(f"| `{label}` | " + " | ".join(str(v) for v in matrix_row) + " |")
        lines.append("")

    p = metrics["policy_behaviour"]
    lines.append("## Deployed policy behaviour (confidence gate applied)")
    lines.append("")
    lines.append(f"- Rows where the system asked for clarification: {p['requires_clarification']}/{metrics['test_rows']}")
    lines.append(f"- Rows answered without clarification: {p['answered_without_clarification']}/{metrics['test_rows']}")
    lines.append(
        f"- Abstention (clarification) rate on non-ambiguous rows: "
        f"{p['unnecessary_clarification_on_clear_rows']}/{p['clear_rows']} "
        f"({p['abstention_rate_on_clear_rows']:.4f})"
    )
    lines.append(
        f"- When the crop head was confident: {p['confident_crop_correct']}/{p['confident_crop_total']} correct"
    )
    lines.append(
        f"- **Accuracy on rows the system chose to answer** "
        f"(all three targets correct): {p['answered_rows_all_three_correct']}/"
        f"{p['answered_without_clarification']} ({p['answered_all_three_accuracy']:.4f})"
    )
    per_target_answered = ", ".join(
        f"{target}={value:.2f}" for target, value in p["answered_per_target_accuracy"].items()
    )
    lines.append(f"- Per-target accuracy on answered rows: {per_target_answered}")
    lines.append(
        f"- Unsupported-crop rows correctly flagged as unsupported: "
        f"{p['unsupported_flagged']}/{p['unsupported_rows']}"
    )
    lines.append("")
    lines.append("Status counts per target:")
    lines.append("")
    for target, counts in p["status_counts"].items():
        rendered = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        lines.append(f"- `{target}`: {rendered}")
    lines.append("")
    lines.append("## Interpretation limits")
    lines.append("")
    lines.append(
        "The test split contains 29 rows. Per-class support is therefore single-digit for most "
        "classes, so per-class precision/recall carry very wide uncertainty; treat them as "
        "directional, not as precise estimates. The dataset is small (196 rows) and this "
        "evaluation characterises a pilot classifier, not a production system."
    )
    lines.append("")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
