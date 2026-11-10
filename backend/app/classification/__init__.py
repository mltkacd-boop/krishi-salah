"""
Module B — Supervised query classification (Phase 4).

Classifies a free-text agricultural query into three independent dimensions:
crop, task and safety topic. Runs entirely in-process with scikit-learn (no
PostgreSQL, no Ollama, no network call), so it works before the database is
reachable and cannot be blocked by LLM availability.

Scope boundary (DEC-001, DEC-010): this module produces *intent labels only*.
It never supplies or approves a pesticide product, dose, PHI, REI, PPE value or
registration status, and it cannot move a knowledge-base record out of the
Phase 3.1 `EDUCATIONAL_ONLY` gate. See `labels.py` for the taxonomy and
`schemas.SafetyPolicy` for the non-approval contract carried on every response.
"""
from app.classification.labels import (
    CROP_CLASSES,
    PILOT_CROPS,
    SAFETY_CLASSES,
    TARGETS,
    TASK_CLASSES,
)
from app.classification.model import (
    MODEL_VERSION,
    ModelNotLoadedError,
    QueryClassifier,
    TargetPrediction,
)
from app.classification.preprocessing import detect_language, normalize_text
from app.classification.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    ModelInfoResponse,
    SafetyPolicy,
    TargetResult,
)
from app.classification.service import (
    ClassifierUnavailableError,
    classify_query,
    get_classifier,
    get_model_info,
)

__all__ = [
    "CROP_CLASSES",
    "TASK_CLASSES",
    "SAFETY_CLASSES",
    "TARGETS",
    "PILOT_CROPS",
    "MODEL_VERSION",
    "QueryClassifier",
    "TargetPrediction",
    "ModelNotLoadedError",
    "ClassifierUnavailableError",
    "normalize_text",
    "detect_language",
    "classify_query",
    "get_classifier",
    "get_model_info",
    "ClassifyRequest",
    "ClassifyResponse",
    "ModelInfoResponse",
    "TargetResult",
    "SafetyPolicy",
]
