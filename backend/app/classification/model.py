"""
Module B — supervised multi-head text classifier.

Design (DEC-011): **one shared TF-IDF feature space + three independent linear
classifiers**, one per target (crop, task, safety topic).

Why shared features but separate classifiers — rather than a single
`MultiOutputClassifier` or one joint 336-way label:
- The three label spaces are logically independent (a query can be
  "mandi price of rice" = crop `rice` + task `out_of_scope`), so a joint label
  would need 7x6x8 combinations for 196 training rows.
- `MultiOutputClassifier` wraps one estimator per output anyway; writing the
  heads explicitly makes per-target class sets, thresholds and confidence
  reporting explicit instead of hidden behind a wrapper.
- Confidence must be reported *per dimension*, because the clarification logic
  asks about the specific dimension that is uncertain ("which crop?" vs
  "are you asking about the waiting period?"). A joint label cannot do that.
- The vectorizer is fitted once on the training text (unsupervised, so no
  label leakage) and shared, which is cheaper and avoids three vocabularies.

Every probability here is an **intent-routing signal**, never agricultural
evidence. See `labels.py` and `schemas.py` for the explicit non-approval
policy carried in every API response.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.classification import labels as L
from app.classification.preprocessing import normalize_text, token_count

MODEL_VERSION = "clf-1.0.0"

# Artifact location: shipped inside the backend package so the API can load it
# without depending on the ml/ directory (which is a training-time concern and
# would not be present in a backend-only deployment).
DEFAULT_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "classifier_v1.joblib"


class ModelNotLoadedError(RuntimeError):
    """Raised when the classifier artifact cannot be found or is corrupt."""


@dataclass(frozen=True)
class TargetPrediction:
    """Prediction for one target dimension."""

    target: str
    label: str
    confidence: float
    margin: float
    status: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)

    @property
    def is_confident(self) -> bool:
        return self.status == L.STATUS_CONFIDENT


def build_feature_union() -> FeatureUnion:
    """
    Word n-grams capture vocabulary ("armyworm", "माहू", "kitnashak"); character
    n-grams capture Hindi inflection and transliteration variation
    ("कीटनाशक"/"कीटनाशको" share substrings, and "keeda"/"keede" share a stem)
    which word-level features miss on a 196-row corpus.
    """
    word = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 1),
        min_df=1,
        sublinear_tf=True,
        strip_accents=None,  # keep Devanagari untouched
        # REQUIRED for Hindi. scikit-learn's default token_pattern is
        # r"(?u)\b\w\w+\b", and `\w` does not match Devanagari combining marks.
        # A word like "धान" is ध + ा + न, i.e. two single-character \w runs
        # separated by a matra, so it cannot match `\w\w+` — the entire Hindi
        # vocabulary is silently dropped and only the char n-grams see Hindi at
        # all. Splitting on whitespace instead keeps whole Devanagari words.
        token_pattern=r"(?u)\S+",
    )
    char = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        sublinear_tf=True,
    )
    return FeatureUnion([("word", word), ("char", char)])


def _build_head() -> Pipeline:
    """
    One-vs-rest logistic regression per target.

    `liblinear` + `C=10` was selected on the *training* split by 5-fold
    cross-validated accuracy (mean across the three targets 0.756; see
    PHASE4_CLASSIFICATION_REPORT.md §Model selection). It was preferred over the
    statistically tied multinomial `lbfgs` alternative because on the
    development split its probabilities are well spread (mean max-probability
    0.649, 0/87 dimensions saturated above 0.95) — the clarification logic is
    only meaningful if confidence is not pinned at 1.0 for every query.

    `class_weight="balanced"` because the label distribution is genuinely
    skewed (`no_safety_topic` 98 rows vs `regulatory_approval` 10); without it
    the rare safety topics would be almost never predicted, which for a safety
    system is the wrong trade.
    """
    return Pipeline(
        steps=[
            (
                "clf",
                LogisticRegression(
                    C=10.0,
                    max_iter=3000,
                    class_weight="balanced",
                    solver="liblinear",
                ),
            )
        ]
    )


class QueryClassifier:
    """
    Fitted multi-head classifier. Construct via `train()` (training script) or
    `load()` (API runtime). Direct construction of an unfitted instance is only
    used by tests that deliberately check error handling.
    """

    def __init__(
        self,
        vectorizer: Optional[FeatureUnion] = None,
        heads: Optional[dict[str, Pipeline]] = None,
        model_version: str = MODEL_VERSION,
        trained_at: Optional[str] = None,
        training_metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.vectorizer = vectorizer
        self.heads: dict[str, Pipeline] = heads or {}
        self.model_version = model_version
        self.trained_at = trained_at
        self.training_metadata = training_metadata or {}

    # ------------------------------------------------------------------ train
    @classmethod
    def train(
        cls,
        texts: Iterable[str],
        targets: dict[str, Iterable[str]],
        model_version: str = MODEL_VERSION,
        training_metadata: Optional[dict[str, Any]] = None,
    ) -> "QueryClassifier":
        """
        Fit the shared vectorizer and one classifier per target.

        `texts` and each `targets[name]` must be aligned and same-length.
        The same `normalize_text` used here is used at inference time — this is
        what prevents train/serve skew.
        """
        normalized = [normalize_text(t) for t in texts]
        if not normalized:
            raise ValueError("Cannot train on an empty dataset.")

        vectorizer = build_feature_union()
        matrix = vectorizer.fit_transform(normalized)

        heads: dict[str, Pipeline] = {}
        for target_name in L.TARGETS:
            if target_name not in targets:
                raise ValueError(f"Missing training labels for target '{target_name}'.")
            y = list(targets[target_name])
            if len(y) != len(normalized):
                raise ValueError(
                    f"Target '{target_name}' has {len(y)} labels for {len(normalized)} texts."
                )
            head = _build_head()
            head.fit(matrix, y)
            heads[target_name] = head

        return cls(
            vectorizer=vectorizer,
            heads=heads,
            model_version=model_version,
            trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            training_metadata=training_metadata or {},
        )

    # ---------------------------------------------------------------- predict
    def is_fitted(self) -> bool:
        return self.vectorizer is not None and all(t in self.heads for t in L.TARGETS)

    def _class_probabilities(self, target: str, row) -> dict[str, float]:
        """Probability per *known* class for one row; unseen classes get 0.0."""
        head = self.heads[target]
        estimator = head.named_steps["clf"]
        raw = estimator.predict_proba(row)[0]
        probabilities = dict.fromkeys(_classes_for(target), 0.0)
        for class_label, probability in zip(estimator.classes_, raw):
            probabilities[str(class_label)] = float(probability)
        return probabilities

    def predict_target(self, normalized: str, target: str, matrix=None) -> TargetPrediction:
        """
        Predict one target with confidence, margin and a status.

        `matrix` lets a caller reuse an already-vectorised query across the three
        heads (the service does this) instead of re-vectorising three times.
        """
        if not self.is_fitted():
            raise ModelNotLoadedError("Classifier is not fitted; no prediction is possible.")

        if token_count(normalized) < L.MIN_TOKENS_FOR_CLASSIFICATION:
            return TargetPrediction(
                target=target,
                label="",
                confidence=0.0,
                margin=0.0,
                status=L.STATUS_UNDETERMINED,
                alternatives=[],
            )

        if matrix is None:
            matrix = self.vectorizer.transform([normalized])

        probabilities = self._class_probabilities(target, matrix)
        ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        top_label, top_confidence = ranked[0]
        second_confidence = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = top_confidence - second_confidence

        status = _derive_status(target, top_label, top_confidence, margin)
        return TargetPrediction(
            target=target,
            label=top_label,
            confidence=round(top_confidence, 4),
            margin=round(margin, 4),
            status=status,
            alternatives=[
                (label, round(probability, 4)) for label, probability in ranked[1:4]
            ],
        )

    def predict_all(self, text: str) -> dict[str, TargetPrediction]:
        """Predict all three targets for one raw query string."""
        if not self.is_fitted():
            raise ModelNotLoadedError("Classifier is not fitted; no prediction is possible.")
        normalized = normalize_text(text)
        if token_count(normalized) < L.MIN_TOKENS_FOR_CLASSIFICATION:
            return {
                target: TargetPrediction(
                    target=target,
                    label="",
                    confidence=0.0,
                    margin=0.0,
                    status=L.STATUS_UNDETERMINED,
                    alternatives=[],
                )
                for target in L.TARGETS
            }
        matrix = self.vectorizer.transform([normalized])
        return {target: self.predict_target(normalized, target, matrix) for target in L.TARGETS}

    def predict_labels(self, texts: Iterable[str]) -> dict[str, np.ndarray]:
        """
        Raw argmax labels per target, for evaluation only.

        Deliberately skips the confidence gate: evaluation must measure the
        classifier, and the gate is reported separately as a policy layer
        (see `ml/classification/evaluate_classifier.py`).
        """
        if not self.is_fitted():
            raise ModelNotLoadedError("Classifier is not fitted; no prediction is possible.")
        normalized = [normalize_text(t) for t in texts]
        matrix = self.vectorizer.transform(normalized)
        return {
            target: np.asarray(self.heads[target].predict(matrix), dtype=object)
            for target in L.TARGETS
        }

    # ------------------------------------------------------------ persistence
    def save(self, path: Optional[Path] = None) -> Path:
        target_path = Path(path) if path else DEFAULT_ARTIFACT_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model_version": self.model_version,
                "trained_at": self.trained_at,
                "vectorizer": self.vectorizer,
                "heads": self.heads,
                "training_metadata": self.training_metadata,
                "label_spaces": {
                    "crop": list(L.CROP_CLASSES),
                    "task": list(L.TASK_CLASSES),
                    "safety_topic": list(L.SAFETY_CLASSES),
                },
            },
            target_path,
        )
        return target_path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "QueryClassifier":
        artifact_path = Path(path) if path else DEFAULT_ARTIFACT_PATH
        if not artifact_path.exists():
            raise ModelNotLoadedError(
                f"Classifier artifact not found at {artifact_path}. "
                f"Run 'python ml/classification/train_classifier.py' to build it."
            )
        try:
            payload = joblib.load(artifact_path)
        except Exception as exc:  # corrupt/truncated file, version mismatch, ...
            raise ModelNotLoadedError(
                f"Classifier artifact at {artifact_path} could not be loaded: {exc}"
            ) from exc

        if not isinstance(payload, dict) or "heads" not in payload or "vectorizer" not in payload:
            raise ModelNotLoadedError(
                f"Classifier artifact at {artifact_path} does not have the expected structure."
            )

        # Guard against a stale artifact trained on a different taxonomy: if the
        # label spaces moved, predictions would silently mean something else.
        expected = {
            "crop": set(L.CROP_CLASSES),
            "task": set(L.TASK_CLASSES),
            "safety_topic": set(L.SAFETY_CLASSES),
        }
        stored = payload.get("label_spaces", {})
        for target, expected_labels in expected.items():
            stored_labels = set(stored.get(target, expected_labels))
            if stored_labels != expected_labels:
                raise ModelNotLoadedError(
                    f"Artifact label space for '{target}' does not match the code "
                    f"(artifact={sorted(stored_labels)}, code={sorted(expected_labels)}). "
                    f"Retrain the model."
                )

        return cls(
            vectorizer=payload["vectorizer"],
            heads=payload["heads"],
            model_version=payload.get("model_version", MODEL_VERSION),
            trained_at=payload.get("trained_at"),
            training_metadata=payload.get("training_metadata", {}),
        )


def _classes_for(target: str) -> tuple[str, ...]:
    """The declared label space for one target (explicit map, not getattr magic)."""
    return {
        "crop": L.CROP_CLASSES,
        "task": L.TASK_CLASSES,
        "safety_topic": L.SAFETY_CLASSES,
    }[target]


def _derive_status(target: str, label: str, confidence: float, margin: float) -> str:
    """
    Map (label, confidence, margin) to a status the caller can act on.

    Order matters: the confidence gate is applied *first*, so an
    out-of-scope or unsupported prediction made with low confidence is reported
    as `ambiguous` (ask the user) rather than as a confident refusal.
    """
    if confidence < L.MIN_CONFIDENCE[target] or margin < L.MIN_MARGIN[target]:
        return L.STATUS_AMBIGUOUS

    if target == "crop":
        if label == L.UNSUPPORTED_CROP_LABEL:
            return L.STATUS_UNSUPPORTED
        if label == L.NO_CROP_LABEL:
            return L.STATUS_NOT_SPECIFIED

    if target == "task" and label == L.OUT_OF_SCOPE_TASK_LABEL:
        return L.STATUS_OUT_OF_SCOPE

    return L.STATUS_CONFIDENT


__all__ = [
    "MODEL_VERSION",
    "DEFAULT_ARTIFACT_PATH",
    "ModelNotLoadedError",
    "TargetPrediction",
    "QueryClassifier",
    "build_feature_union",
]
