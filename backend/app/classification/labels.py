"""
Module B — Supervised classification: label taxonomy and decision thresholds.

Single source of truth for the three *independent* label spaces the classifier
predicts (crop, task, safety topic). See DEC-011 for why these are three
separate heads rather than one joint label.

IMPORTANT (safety boundary, DEC-001 / DEC-010):
These labels are **routing signals only**. A predicted label such as
`safety_topic="dosage"` states what the user is *asking about*; it never
supplies, approves or implies a dose, PHI, REI, PPE value or registration
status. No module may treat a classification result as agricultural evidence,
and no classification result can move a knowledge-base record out of the
Phase 3.1 `EDUCATIONAL_ONLY` gate.
"""
from __future__ import annotations

from typing import Final

# --- Crop label space ------------------------------------------------------
# The five pilot crops (DEC-005) plus two *explicit non-answers*. The two
# extra labels exist so an unsupported or crop-less query is recognised and
# reported honestly instead of being forced into one of the five pilot crops.
PILOT_CROPS: Final[tuple[str, ...]] = ("rice", "wheat", "maize", "cotton", "tomato")

UNSUPPORTED_CROP_LABEL: Final[str] = "unsupported_crop"
NO_CROP_LABEL: Final[str] = "no_crop"

CROP_CLASSES: Final[tuple[str, ...]] = (
    *PILOT_CROPS,
    UNSUPPORTED_CROP_LABEL,
    NO_CROP_LABEL,
)

# --- Task label space ------------------------------------------------------
TASK_CLASSES: Final[tuple[str, ...]] = (
    "pest_identification",
    "pest_management",
    "disease_management",
    "product_information",
    "general_guidance",
    "out_of_scope",
)

OUT_OF_SCOPE_TASK_LABEL: Final[str] = "out_of_scope"

# Tasks that are only meaningful when a specific crop is known. If the crop is
# not identifiable for one of these, the caller must clarify rather than guess.
CROP_DEPENDENT_TASKS: Final[frozenset[str]] = frozenset(
    {"pest_identification", "pest_management", "disease_management"}
)

# --- Safety-topic label space ---------------------------------------------
SAFETY_CLASSES: Final[tuple[str, ...]] = (
    "dosage",
    "phi",
    "rei",
    "ppe",
    "toxicity",
    "regulatory_approval",
    "general_safety",
    "no_safety_topic",
)

NO_SAFETY_TOPIC_LABEL: Final[str] = "no_safety_topic"

TARGETS: Final[tuple[str, str, str]] = ("crop", "task", "safety_topic")

# --- Confidence / margin gating -------------------------------------------
# Set a priori (NOT tuned on the held-out test split, which would be leakage).
# The 0.15 margin requirement is the important one for this task: on a 5-8
# class text problem a single strong lexical cue can push one class to ~0.45
# while the runner-up is ~0.40, and presenting that as a definite answer would
# be misleading. Values were sanity-checked against the development split only;
# see PHASE4_CLASSIFICATION_REPORT.md §Threshold selection.
MIN_CONFIDENCE: Final[dict[str, float]] = {
    "crop": 0.40,
    "task": 0.40,
    "safety_topic": 0.40,
}
MIN_MARGIN: Final[dict[str, float]] = {
    "crop": 0.15,
    "task": 0.15,
    "safety_topic": 0.15,
}

# A query with fewer than this many tokens carries too little signal to
# classify; it is reported as `undetermined` and always triggers clarification.
MIN_TOKENS_FOR_CLASSIFICATION: Final[int] = 2

# Vagueness guard (not a classifier, a refusal-to-guess rule).
#
# A short query with no crop, only generic intent and no specific safety
# dimension ("Is it safe?", "Need help with spraying", "फसल में समस्या है")
# can be labelled confidently by any bag-of-words model — there are simply too
# few words for the wrong reading to look unlikely. Answering it would be a
# guess dressed as a result. When all three of the conditions below hold, the
# service asks for detail instead of answering:
#   no crop identified + task is general guidance + safety topic is generic
#   + the query is no longer than this many tokens.
# The token limit is deliberately small: "What is integrated pest management?"
# (5 tokens) is a legitimate general question and must still be answered.
VAGUE_QUERY_MAX_TOKENS: Final[int] = 4

# Safety labels that carry no specific safety dimension.
GENERIC_SAFETY_LABELS: Final[frozenset[str]] = frozenset(
    {"general_safety", "no_safety_topic"}
)

# --- Status vocabulary ----------------------------------------------------
STATUS_CONFIDENT: Final[str] = "confident"
STATUS_AMBIGUOUS: Final[str] = "ambiguous"
STATUS_UNSUPPORTED: Final[str] = "unsupported"
STATUS_OUT_OF_SCOPE: Final[str] = "out_of_scope"
STATUS_NOT_SPECIFIED: Final[str] = "not_specified"
STATUS_UNDETERMINED: Final[str] = "undetermined"

# --- Human-readable names (frontend / clarification text) ------------------
CROP_DISPLAY: Final[dict[str, str]] = {
    "rice": "Rice",
    "wheat": "Wheat",
    "maize": "Maize",
    "cotton": "Cotton",
    "tomato": "Tomato",
    UNSUPPORTED_CROP_LABEL: "A crop outside the pilot scope",
    NO_CROP_LABEL: "No crop specified",
}

TASK_DISPLAY: Final[dict[str, str]] = {
    "pest_identification": "Identifying a pest",
    "pest_management": "Pest management",
    "disease_management": "Disease management",
    "product_information": "Product information",
    "general_guidance": "General agricultural guidance",
    "out_of_scope": "Outside the advisory scope",
}

SAFETY_DISPLAY: Final[dict[str, str]] = {
    "dosage": "Dosage / application quantity",
    "phi": "Pre-harvest interval (PHI)",
    "rei": "Re-entry interval (REI)",
    "ppe": "Protective equipment (PPE)",
    "toxicity": "Toxicity / hazard",
    "regulatory_approval": "Regulatory approval / registration",
    "general_safety": "General pesticide safety",
    "no_safety_topic": "General farming (no safety topic)",
}

DISPLAY: Final[dict[str, dict[str, str]]] = {
    "crop": CROP_DISPLAY,
    "task": TASK_DISPLAY,
    "safety_topic": SAFETY_DISPLAY,
}


def supported_crop_label(label: str) -> bool:
    """True only for the five pilot crops — the only crops Phase 3-4 has data for."""
    return label in PILOT_CROPS


__all__ = [
    "PILOT_CROPS",
    "CROP_CLASSES",
    "TASK_CLASSES",
    "SAFETY_CLASSES",
    "TARGETS",
    "UNSUPPORTED_CROP_LABEL",
    "NO_CROP_LABEL",
    "OUT_OF_SCOPE_TASK_LABEL",
    "NO_SAFETY_TOPIC_LABEL",
    "CROP_DEPENDENT_TASKS",
    "MIN_CONFIDENCE",
    "MIN_MARGIN",
    "MIN_TOKENS_FOR_CLASSIFICATION",
    "VAGUE_QUERY_MAX_TOKENS",
    "GENERIC_SAFETY_LABELS",
    "STATUS_CONFIDENT",
    "STATUS_AMBIGUOUS",
    "STATUS_UNSUPPORTED",
    "STATUS_OUT_OF_SCOPE",
    "STATUS_NOT_SPECIFIED",
    "STATUS_UNDETERMINED",
    "CROP_DISPLAY",
    "TASK_DISPLAY",
    "SAFETY_DISPLAY",
    "DISPLAY",
    "supported_crop_label",
]
