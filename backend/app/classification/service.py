"""
Module B — classification service (model loading + response assembly).

The service is the only place that turns raw model output into the API
contract. It owns three decisions that the model itself must not make:

1. **When to ask a clarifying question.** A low-confidence dimension is not an
   error; it is a request for the user to disambiguate. This keeps the system
   from guessing a crop, task or safety topic.
2. **What to say when a query is out of scope.** An unsupported crop is a
   confident, correct answer ("this pilot cannot advise on sugarcane"), which
   is different from uncertainty.
3. **Which language to phrase the reply in.** English or Hindi (DEC-003), based
   on the heuristic language detection, so the clarification is actually
   usable by the farmer who asked.

Model loading is cached per process and performed lazily, so importing the app
never fails just because the artifact is absent — but a *classification
request* against a missing artifact fails loudly with 503 rather than silently
returning a made-up answer.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.classification import labels as L
from app.classification.model import (
    DEFAULT_ARTIFACT_PATH,
    ModelNotLoadedError,
    QueryClassifier,
    TargetPrediction,
)
from app.classification.preprocessing import (
    LANGUAGE_HINDI,
    detect_language,
    normalize_text,
    token_count,
)
from app.classification.schemas import (
    AlternativeLabel,
    ClassifyResponse,
    ModelInfoResponse,
    SafetyPolicy,
    TargetResult,
)

logger = logging.getLogger("pesticide_advisory.classification")

ARTIFACT_ENV_VAR = "CLASSIFIER_ARTIFACT_PATH"


class ClassifierUnavailableError(RuntimeError):
    """Raised when the model artifact cannot be loaded; surfaced to clients as HTTP 503."""


def _artifact_path() -> Path:
    override = os.environ.get(ARTIFACT_ENV_VAR)
    return Path(override) if override else DEFAULT_ARTIFACT_PATH


@lru_cache(maxsize=1)
def get_classifier() -> QueryClassifier:
    """
    Load and cache the fitted classifier for this process.

    Cached because loading a joblib artifact on every request would be wasteful;
    safe because the classifier is immutable once loaded.
    """
    path = _artifact_path()
    try:
        classifier = QueryClassifier.load(path)
    except ModelNotLoadedError as exc:
        logger.error("Classification model unavailable: %s", exc)
        raise ClassifierUnavailableError(str(exc)) from exc
    logger.info(
        "Classification model loaded: version=%s trained_at=%s path=%s",
        classifier.model_version,
        classifier.trained_at,
        path,
    )
    return classifier


def reset_classifier_cache() -> None:
    """Clear the cached model (used by tests and after retraining)."""
    get_classifier.cache_clear()


# --- Clarification / scope wording (English + Hindi, DEC-003) --------------
_PROMPTS: dict[str, dict[str, str]] = {
    "crop": {
        "en": "Which crop is this about? This assistant covers rice, wheat, maize, cotton and tomato.",
        "hi": "यह किस फसल के बारे में है? यह सहायक धान, गेहूं, मक्का, कपास और टमाटर के लिए जानकारी देता है।",
    },
    "task": {
        "en": "Could you say a little more about what you need — identifying a pest, managing it, or information about a specific product?",
        "hi": "कृपया थोड़ा स्पष्ट करें — आप कीट की पहचान चाहते हैं, उसका नियंत्रण चाहते हैं, या किसी उत्पाद की जानकारी चाहते हैं?",
    },
    "safety": {
        "en": "Which safety point do you mean — the dose, the waiting period before harvest, re-entry after spraying, protective equipment, or toxicity?",
        "hi": "आप सुरक्षा के किस बिंदु के बारे में पूछ रहे हैं — मात्रा, कटाई से पहले प्रतीक्षा अवधि, छिड़काव के बाद प्रवेश, सुरक्षा कपड़े, या जहरीलापन?",
    },
    "undetermined": {
        "en": "Please describe your crop and the problem in a few more words so I can help.",
        "hi": "कृपया अपनी फसल और समस्या को कुछ और शब्दों में बताएं ताकि मैं मदद कर सकूं।",
    },
    "vague": {
        "en": (
            "Could you tell me which crop this is about and what you have noticed — for "
            "example the symptoms, or the product you used?"
        ),
        "hi": (
            "कृपया बताएं कि यह किस फसल के बारे में है और आपने क्या देखा है — जैसे लक्षण, "
            "या आपने कौन सा उत्पाद इस्तेमाल किया।"
        ),
    },
}

_SCOPE_MESSAGES: dict[str, dict[str, str]] = {
    "unsupported_crop": {
        "en": (
            "This pilot covers rice, wheat, maize, cotton and tomato only, so I cannot advise "
            "on this crop. I will not guess a recommendation for a crop outside that scope."
        ),
        "hi": (
            "यह पायलट केवल धान, गेहूं, मक्का, कपास और टमाटर के लिए है, इसलिए मैं इस फसल पर "
            "सलाह नहीं दे सकता। मैं इस दायरे से बाहर की फसल के लिए अनुमान नहीं लगाऊंगा।"
        ),
    },
    "out_of_scope": {
        "en": (
            "That question is outside what this assistant covers. It focuses on safe pesticide "
            "use for rice, wheat, maize, cotton and tomato — for market prices, weather, loans "
            "or machinery please use the relevant official service."
        ),
        "hi": (
            "यह प्रश्न इस सहायक के दायरे से बाहर है। यह धान, गेहूं, मक्का, कपास और टमाटर में "
            "कीटनाशक के सुरक्षित उपयोग पर केंद्रित है — मंडी भाव, मौसम, ऋण या मशीनरी के लिए "
            "कृपया संबंधित सरकारी सेवा का उपयोग करें।"
        ),
    },
}


def _language_key(detected: str) -> str:
    """Hindi and Hinglish users get the Hindi wording; everyone else English."""
    return "hi" if detected == LANGUAGE_HINDI else "en"


def _to_target_result(prediction: TargetPrediction, target: str) -> TargetResult:
    display = L.DISPLAY[target].get(prediction.label) if prediction.label else None
    return TargetResult(
        label=prediction.label or None,
        display_label=display,
        confidence=prediction.confidence,
        margin=prediction.margin,
        status=prediction.status,  # type: ignore[arg-type]
        alternatives=[
            AlternativeLabel(label=label, confidence=confidence)
            for label, confidence in prediction.alternatives
        ],
    )


def _clarification_needs(
    crop: TargetPrediction,
    task: TargetPrediction,
    safety: TargetPrediction,
    normalized_token_count: int,
) -> list[str]:
    """
    Decide which dimensions need the user to disambiguate.

    Note the asymmetry: a crop that is merely `not_specified` is fine for a
    generic safety question ("what PPE should I wear?") but unacceptable for a
    crop-specific pest question, where answering without knowing the crop would
    invite a wrong recommendation.
    """
    if L.STATUS_UNDETERMINED in (crop.status, task.status, safety.status):
        return ["undetermined"]

    # Refuse to answer a query that has no subject at all — see
    # labels.VAGUE_QUERY_MAX_TOKENS for why confidence alone cannot catch this.
    if (
        crop.status in (L.STATUS_NOT_SPECIFIED, L.STATUS_AMBIGUOUS)
        and task.label == "general_guidance"
        and safety.label in L.GENERIC_SAFETY_LABELS
        and normalized_token_count <= L.VAGUE_QUERY_MAX_TOKENS
    ):
        return ["vague"]

    needs: list[str] = []

    # The crop only changes the answer for crop-specific agronomic tasks. Asking
    # "which crop?" after a generic question ("what PPE should I wear?") is
    # noise, and would push the abstention rate up without making any answer
    # safer — so crop uncertainty is surfaced in the response (`status`) but
    # only *forces* a question when the task actually depends on it.
    if task.label in L.CROP_DEPENDENT_TASKS and crop.status in (
        L.STATUS_AMBIGUOUS,
        L.STATUS_NOT_SPECIFIED,
    ):
        needs.append("crop")

    if task.status == L.STATUS_AMBIGUOUS:
        needs.append("task")
    if safety.status == L.STATUS_AMBIGUOUS:
        needs.append("safety")
    return needs


def classify_query(query: str) -> ClassifyResponse:
    """
    Classify one query into crop / task / safety topic and assemble the response.

    Raises `ClassifierUnavailableError` if the model artifact is missing, so the
    API can return an honest 503 instead of a fabricated prediction.
    """
    classifier = get_classifier()

    normalized = normalize_text(query)
    detected = detect_language(query)
    predictions = classifier.predict_all(query)

    crop_pred = predictions["crop"]
    task_pred = predictions["task"]
    safety_pred = predictions["safety_topic"]

    needs = _clarification_needs(
        crop_pred, task_pred, safety_pred, token_count(normalized)
    )
    language_key = _language_key(detected)

    clarification_message = None
    if needs:
        clarification_message = " ".join(_PROMPTS[need][language_key] for need in needs)

    unsupported = crop_pred.status == L.STATUS_UNSUPPORTED
    out_of_scope = task_pred.status == L.STATUS_OUT_OF_SCOPE

    scope_message = None
    if unsupported:
        scope_message = _SCOPE_MESSAGES["unsupported_crop"][language_key]
    elif out_of_scope:
        scope_message = _SCOPE_MESSAGES["out_of_scope"][language_key]

    return ClassifyResponse(
        query=query,
        detected_language=detected,  # type: ignore[arg-type]
        crop=_to_target_result(crop_pred, "crop"),
        task=_to_target_result(task_pred, "task"),
        safety_topic=_to_target_result(safety_pred, "safety_topic"),
        requires_clarification=bool(needs),
        clarification_message=clarification_message,
        unsupported=unsupported,
        out_of_scope=out_of_scope,
        scope_message=scope_message,
        model_version=classifier.model_version,
        safety_policy=SafetyPolicy(),
    )


def get_model_info() -> ModelInfoResponse:
    """Model identity and thresholds, for verifiability. Not shown to ordinary users."""
    classifier = get_classifier()
    return ModelInfoResponse(
        model_version=classifier.model_version,
        trained_at=classifier.trained_at,
        classifier_type=(
            "TF-IDF (word 1-2 grams + char_wb 3-5 grams) with one multinomial "
            "logistic-regression head per target label space"
        ),
        targets={
            "crop": list(L.CROP_CLASSES),
            "task": list(L.TASK_CLASSES),
            "safety_topic": list(L.SAFETY_CLASSES),
        },
        thresholds={
            target: {
                "min_confidence": L.MIN_CONFIDENCE[target],
                "min_margin": L.MIN_MARGIN[target],
            }
            for target in L.TARGETS
        },
        training_metadata=classifier.training_metadata,
        note=(
            "Labels are intent-routing signals. The model contains no dosage, PHI, REI, PPE or "
            "registration facts and cannot approve a recommendation."
        ),
    )


__all__ = [
    "classify_query",
    "get_classifier",
    "get_model_info",
    "reset_classifier_cache",
    "ClassifierUnavailableError",
    "ARTIFACT_ENV_VAR",
]
