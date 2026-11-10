"""
Shared dataset loading, validation and splitting for Phase 4 (Module B).

Both `train_classifier.py` and `evaluate_classifier.py` import from here so the
split is defined in exactly one place. If training and evaluation computed their
own splits, a metric could be reported against rows the model had seen — the
data-leakage failure this module exists to prevent.

Guarantees enforced here (each raises, so a violation cannot be trained around):
1. Every label is a member of the declared taxonomy in `app.classification.labels`.
2. Query texts are unique across the whole dataset (after normalisation).
3. Train / dev / test contain **no shared query text** — no duplicate rows and
   no near-identical normalised forms can appear on both sides.
4. The split is reproducible from `SPLIT_SEED` alone.
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.classification import labels as L  # noqa: E402  (path bootstrap must run first)
from app.classification.preprocessing import normalize_text  # noqa: E402

DATASET_PATH = REPO_ROOT / "ml" / "classification" / "dataset" / "queries.csv"
ARTIFACTS_DIR = REPO_ROOT / "ml" / "classification" / "artifacts"
REPORTS_DIR = REPO_ROOT / "ml" / "classification" / "reports"

SPLIT_SEED = 42
TEST_FRACTION = 0.15
DEV_FRACTION = 0.15

TARGET_COLUMNS = ("crop", "task", "safety_topic")
VALID_LABELS = {
    "crop": set(L.CROP_CLASSES),
    "task": set(L.TASK_CLASSES),
    "safety_topic": set(L.SAFETY_CLASSES),
}
VALID_LANGUAGES = {"en", "hi", "hi-latn"}


@dataclass(frozen=True)
class QueryRow:
    row_id: str
    text: str
    language: str
    crop: str
    task: str
    safety_topic: str
    notes: str

    @property
    def normalized(self) -> str:
        return normalize_text(self.text)

    @property
    def labels(self) -> dict[str, str]:
        return {
            "crop": self.crop,
            "task": self.task,
            "safety_topic": self.safety_topic,
        }


@dataclass(frozen=True)
class Split:
    train: list[QueryRow]
    dev: list[QueryRow]
    test: list[QueryRow]

    def ids(self) -> dict[str, list[str]]:
        return {
            "train": [row.row_id for row in self.train],
            "dev": [row.row_id for row in self.dev],
            "test": [row.row_id for row in self.test],
        }


def load_dataset(path: Path | None = None) -> list[QueryRow]:
    """Read and fully validate `queries.csv`."""
    dataset_path = Path(path) if path else DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    rows: list[QueryRow] = []
    with dataset_path.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = QueryRow(
                row_id=raw["id"].strip(),
                text=raw["text"].strip(),
                language=raw["language"].strip(),
                crop=raw["crop"].strip(),
                task=raw["task"].strip(),
                safety_topic=raw["safety_topic"].strip(),
                notes=(raw.get("notes") or "").strip(),
            )
            _validate_row(row)
            rows.append(row)

    if not rows:
        raise ValueError(f"Dataset at {dataset_path} is empty.")

    _assert_no_duplicate_texts(rows)
    return rows


def _validate_row(row: QueryRow) -> None:
    if not row.text:
        raise ValueError(f"Row {row.row_id} has empty text.")
    if row.language not in VALID_LANGUAGES:
        raise ValueError(f"Row {row.row_id} has unknown language '{row.language}'.")
    for target in TARGET_COLUMNS:
        label = getattr(row, target)
        if label not in VALID_LABELS[target]:
            raise ValueError(
                f"Row {row.row_id} has label '{label}' which is not in the "
                f"'{target}' taxonomy. Refusing to train on an undeclared label."
            )


def _assert_no_duplicate_texts(rows: list[QueryRow]) -> None:
    seen: dict[str, str] = {}
    for row in rows:
        key = row.normalized
        if key in seen:
            raise ValueError(
                f"Duplicate query text: row {row.row_id} duplicates row {seen[key]} "
                f"after normalisation ({row.text!r})."
            )
        seen[key] = row.row_id


def make_splits(rows: list[QueryRow], seed: int = SPLIT_SEED) -> Split:
    """
    Deterministic ~70/15/15 split with **guaranteed label coverage**.

    Why not `train_test_split(stratify=...)`? Stratifying on one column only
    balances that column. This dataset has three label spaces with different
    rare classes (task `out_of_scope` n=12, safety `regulatory_approval` n=10),
    and a single-column stratified draw can leave an entire class absent from
    the test split — which would silence exactly the rare classes a safety
    project most needs to measure, or make scikit-learn raise.

    Instead this uses a deterministic greedy allocation: rows are shuffled with
    `seed`, then each row is placed in the split that currently has the largest
    *relative deficit* for its three labels (plus a capacity term so splits fill
    evenly). Coverage of every label in every split is then asserted; a
    violation raises rather than silently producing a degenerate evaluation.

    Reproducible from `seed` alone; `assert_no_leakage` still runs afterwards.
    """
    import random
    from collections import Counter

    n_total = len(rows)
    n_test = max(1, round(n_total * TEST_FRACTION))
    n_dev = max(1, round(n_total * DEV_FRACTION))
    n_train = n_total - n_test - n_dev

    capacities = {"train": n_train, "dev": n_dev, "test": n_test}
    fractions = {name: count / n_total for name, count in capacities.items()}
    totals = {
        target: Counter(getattr(row, target) for row in rows) for target in TARGET_COLUMNS
    }
    assigned = {
        name: {target: Counter() for target in TARGET_COLUMNS} for name in capacities
    }

    order = list(rows)
    random.Random(seed).shuffle(order)

    buckets: dict[str, list[QueryRow]] = {"train": [], "dev": [], "test": []}

    for row in order:
        best_split: str | None = None
        best_score = float("-inf")
        for name in ("test", "dev", "train"):
            if capacities[name] <= 0:
                continue
            score = 0.0
            for target in TARGET_COLUMNS:
                label = getattr(row, target)
                wanted = totals[target][label] * fractions[name]
                already = assigned[name][target][label]
                # Relative deficit: strongly prefers a split that still "needs"
                # this rare label, which is what guarantees rare-class coverage.
                score += (wanted - already) / max(wanted, 1e-9)
            # Fill splits proportionally rather than starving one of them.
            score += 0.5 * (capacities[name] / n_total)
            if score > best_score:
                best_score, best_split = score, name

        if best_split is None:
            raise AssertionError("Split allocation ran out of capacity; check fractions.")
        buckets[best_split].append(row)
        capacities[best_split] -= 1
        for target in TARGET_COLUMNS:
            assigned[best_split][target][getattr(row, target)] += 1

    split = Split(train=buckets["train"], dev=buckets["dev"], test=buckets["test"])
    assert_no_leakage(split)
    _assert_full_label_coverage(split)
    return split


def _assert_full_label_coverage(split: Split) -> None:
    """
    Every declared label must appear in every split.

    Without this, an evaluation can look fine while silently never testing a
    class — the failure mode this whole module exists to prevent.
    """
    problems: list[str] = []
    for split_name in ("train", "dev", "test"):
        rows = getattr(split, split_name)
        for target in TARGET_COLUMNS:
            present = {getattr(row, target) for row in rows}
            missing = VALID_LABELS[target] - present
            if missing:
                problems.append(f"{split_name}/{target} missing {sorted(missing)}")
    if problems:
        raise AssertionError(
            "Splits do not cover every label (increase dataset size or relax "
            f"fractions): {'; '.join(problems)}"
        )


def assert_no_leakage(split: Split) -> None:
    """
    Hard failure if any normalised query text appears in more than one split.

    This is the concrete implementation of "avoid duplicate examples across
    training and testing" — it is checked, not assumed.
    """
    normalized: dict[str, list[tuple[str, str]]] = {}
    for split_name in ("train", "dev", "test"):
        for row in getattr(split, split_name):
            normalized.setdefault(row.normalized, []).append((split_name, row.row_id))

    overlaps = {key: value for key, value in normalized.items() if len(value) > 1}
    if overlaps:
        details = "; ".join(
            f"{key!r}: {value}" for key, value in list(overlaps.items())[:5]
        )
        raise AssertionError(f"Data leakage between splits: {details}")

    seen_ids: set[str] = set()
    for split_name in ("train", "dev", "test"):
        for row in getattr(split, split_name):
            if row.row_id in seen_ids:
                raise AssertionError(f"Row {row.row_id} appears in more than one split.")
            seen_ids.add(row.row_id)


def label_distribution(rows: list[QueryRow]) -> dict[str, dict[str, int]]:
    """Per-target label counts, used for the training metadata and the report."""
    distribution: dict[str, dict[str, int]] = {}
    for target in TARGET_COLUMNS:
        counts: dict[str, int] = {label: 0 for label in VALID_LABELS[target]}
        for row in rows:
            counts[getattr(row, target)] += 1
        distribution[target] = counts
    return distribution


def print_split_summary(split: Split) -> None:
    print(f"Split sizes: train={len(split.train)} dev={len(split.dev)} test={len(split.test)}")
    for split_name in ("train", "dev", "test"):
        rows = getattr(split, split_name)
        dist = label_distribution(rows)
        print(f"  [{split_name}] crop={dist['crop']}")
    missing = [
        (target, label)
        for target in TARGET_COLUMNS
        for label in VALID_LABELS[target]
        if not any(getattr(row, target) == label for row in split.test)
    ]
    if missing:
        print(f"  NOTE: labels absent from the test split (metrics will show support=0): {missing}")


__all__ = [
    "REPO_ROOT",
    "BACKEND_DIR",
    "DATASET_PATH",
    "ARTIFACTS_DIR",
    "REPORTS_DIR",
    "SPLIT_SEED",
    "TARGET_COLUMNS",
    "VALID_LABELS",
    "QueryRow",
    "Split",
    "load_dataset",
    "make_splits",
    "assert_no_leakage",
    "label_distribution",
    "print_split_summary",
]
