"""
Module B — Pydantic request/response contracts for the classification API.

Two things are deliberately explicit in the response shape:

1. **Per-dimension status.** A caller never receives a bare label with no
   indication of how sure the model is; every dimension carries `status`, and
   an `ambiguous` dimension is a first-class, expected outcome rather than an
   error.
2. **A non-approval policy block.** Prediction output is *intent routing*, not
   agricultural advice. `SafetyPolicy` states in the machine-readable response
   that classification approves no pesticide recommendation and cannot lift the
   Phase 3.1 `EDUCATIONAL_ONLY` gate. Putting this in the schema (rather than
   only in documentation) means every consumer sees it, including a future
   frontend or RAG module.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.classification.labels import STATUS_UNDETERMINED

MAX_QUERY_LENGTH = 1000


class ClassifyRequest(BaseModel):
    """Input query for supervised classification."""

    # `extra="forbid"` so a caller cannot silently send an ignored field (e.g. a
    # stale parameter from an older client); `protected_namespaces=()` is needed
    # because the response legitimately uses the field name `model_version`.
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    query: str = Field(
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="The user's question, in English, Hindi (Devanagari) or romanised Hindi.",
        examples=["How many days before harvest should I stop spraying in paddy?"],
    )

    @field_validator("query")
    @classmethod
    def _query_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must contain at least one non-whitespace character")
        return stripped


class AlternativeLabel(BaseModel):
    """A runner-up label, so a caller can see what else was plausible."""

    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class TargetResult(BaseModel):
    """Prediction for one label dimension (crop, task or safety topic)."""

    label: Optional[str] = Field(
        default=None,
        description="Predicted label, or null when the query is too short to classify "
        "(status='undetermined').",
    )
    display_label: Optional[str] = Field(
        default=None, description="Human-readable label for UI display."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Top-class probability estimate.")
    margin: float = Field(
        ge=0.0,
        le=1.0,
        description="Top probability minus the runner-up. A small margin means two labels "
        "were nearly equally plausible.",
    )
    status: Literal[
        "confident",
        "ambiguous",
        "unsupported",
        "out_of_scope",
        "not_specified",
        "undetermined",
    ] = Field(
        default=STATUS_UNDETERMINED,
        description="'confident' only when confidence and margin both clear the thresholds. "
        "'unsupported' = a real crop outside the five-crop pilot scope. 'not_specified' = no "
        "crop was named. 'out_of_scope' = the request is beyond this assistant's remit.",
    )
    alternatives: list[AlternativeLabel] = Field(default_factory=list)


class SafetyPolicy(BaseModel):
    """
    Machine-readable statement of what a classification result does NOT do.

    This is intentionally part of the response body, not a comment or a doc
    note, so no downstream consumer can be unaware of it.
    """

    approves_pesticide_recommendation: Literal[False] = Field(
        default=False,
        description="Always false. Classification assigns intent labels only; it never "
        "approves a pesticide use, dose, PHI, REI, PPE value or registration status.",
    )
    can_override_educational_only_gate: Literal[False] = Field(
        default=False,
        description="Always false. A classification result cannot change a knowledge-base "
        "record's Phase 3.1 advisory_status.",
    )
    advisory_gate: str = Field(
        default="UNCHANGED_EDUCATIONAL_ONLY_UNTIL_SAFETY_EVIDENCE",
        description="The Phase 3.1 gate that continues to apply downstream of classification.",
    )
    note: str = Field(
        default=(
            "Classification identifies what the user is asking about. It is not agricultural "
            "evidence and must not be presented as a recommendation. Any pesticide guidance "
            "still requires a source-verified knowledge-base record, and records whose PHI/REI/PPE "
            "are not published in their source remain EDUCATIONAL_ONLY."
        )
    )


class ClassifyResponse(BaseModel):
    """Structured classification output."""

    model_config = ConfigDict(protected_namespaces=())

    query: str
    detected_language: Literal["en", "hi", "hi-latn", "unknown"]
    crop: TargetResult
    task: TargetResult
    safety_topic: TargetResult

    requires_clarification: bool = Field(
        description="True when at least one dimension was too uncertain to act on, or the "
        "crop is needed but was not identified."
    )
    clarification_message: Optional[str] = Field(
        default=None,
        description="A user-facing question to resolve the uncertainty, in the detected "
        "language. Null when no clarification is needed.",
    )
    unsupported: bool = Field(
        default=False,
        description="True when the query concerns a real crop outside the five-crop pilot scope.",
    )
    out_of_scope: bool = Field(
        default=False,
        description="True when the query is outside this assistant's remit entirely.",
    )
    scope_message: Optional[str] = Field(
        default=None,
        description="A user-facing explanation when the query is unsupported or out of scope. "
        "Distinct from clarification_message: here the system is confident, it is simply "
        "declining to answer beyond its scope.",
    )

    model_version: str
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)


class ModelInfoResponse(BaseModel):
    """Model identity/metadata for verifiability (not shown to ordinary users)."""

    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    trained_at: Optional[str]
    classifier_type: str
    targets: dict[str, list[str]]
    thresholds: dict[str, dict[str, float]]
    training_metadata: dict
    note: str


__all__ = [
    "ClassifyRequest",
    "ClassifyResponse",
    "TargetResult",
    "AlternativeLabel",
    "SafetyPolicy",
    "ModelInfoResponse",
    "MAX_QUERY_LENGTH",
]
