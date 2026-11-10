"""
Phase 6 — RAG response contract.

Design notes that matter for review:

* `generation_mode` is in the response because it is a safety-relevant fact. It is
  always "extractive": every sentence of agricultural content is assembled from
  knowledge-base fields that were themselves transcribed from a named source.
  No generative model is called, so no model can invent a dose, a PHI/REI/PPE
  value or a registration status. A future LLM composer must set a different
  value here, which makes the change visible to any consumer.
* `usage_policy` and `advisory_status` travel with the answer, not in a doc
  comment, so a caller cannot render the text without also receiving the gate.
* `outcome` is a closed enum: there is no "partially answered" state that could
  hide an unsupported claim.
* `safety_contradiction` was added in Phase 7. The rule engine distinguishes "the
  sources disagree" (ESCALATE_CONTRADICTION) from "there is no record"
  (`insufficient_evidence`) and "I cannot tell what is being asked"
  (`needs_clarification`); folding a contradiction into either of those would
  lose the reason the answer was withheld.
* `rule_findings` and `rule_trace` make the Phase 7 verdict part of the response
  rather than a server-side log line, so a caller can show exactly which rule
  fired and on which fields.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_QUERY_LENGTH = 1000

# One definition, two forms: the Literal used by Pydantic, and a runtime tuple so
# tests and callers can assert membership without duplicating the list.
RAG_OUTCOMES = (
    "answered",
    "needs_clarification",
    "out_of_scope",
    "unsupported_crop",
    "insufficient_evidence",
    "safety_value_not_published",
    "no_regulatory_verification",
    "safety_contradiction",
)
RagOutcome = Literal[
    "answered",
    "needs_clarification",
    "out_of_scope",
    "unsupported_crop",
    "insufficient_evidence",
    "safety_value_not_published",
    "no_regulatory_verification",
    "safety_contradiction",
]

ConfidenceLabel = Literal["low", "medium", "high"]
AdvisoryStatus = Literal["ACTIONABLE_WITH_EVIDENCE", "EDUCATIONAL_ONLY"]


class RagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    language: Optional[Literal["en", "hi"]] = Field(
        default=None,
        description="Force the answer language. Omit to follow the detected query language.",
    )
    max_evidence: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    """Where a statement came from. Every answered response has at least one."""

    source_id: str
    title: str
    authority: str
    url: str
    retrieved_date: str
    reliability_tier: str
    verification_status: str = Field(
        description="VERIFIED_SOURCE_RECOMMENDATION means 'transcribed correctly from this "
        "page'. It never means CIB&RC registration or regulatory approval."
    )
    provenance_sha256: Optional[str] = Field(
        default=None,
        description="First 16 hex chars of the audited document digest, when a provenance "
        "record exists. Proves integrity of the fetched bytes, not authenticity.",
    )
    chunk_refs: list[str] = Field(default_factory=list)
    record_ids: list[str] = Field(
        default_factory=list,
        description="Knowledge-base records this source supports in the answer. One source "
        "can back several records (e.g. one TNAU cotton page set).",
    )


class SafetyDisclosure(BaseModel):
    """The record-level PHI/REI/PPE state, quoted or explicitly declared absent."""

    field: Literal["phi", "rei", "ppe"]
    status: Literal["PUBLISHED", "NOT_PUBLISHED_IN_SOURCE"]
    value: Optional[str] = None
    note: Optional[str] = None


class EvidenceItem(BaseModel):
    chunk_ref: str
    chunk_type: str
    score: float
    approved_use_id: Optional[str]
    advisory_status: Optional[AdvisoryStatus]


class RagResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    query: str
    answer_language: Literal["en", "hi"]
    outcome: RagOutcome

    answer: Optional[str] = Field(
        default=None, description="Grounded answer text. Null for every non-'answered' outcome."
    )
    sections: list[dict] = Field(default_factory=list)
    message: Optional[str] = Field(
        default=None, description="Explanation for a non-answered outcome, in the answer language."
    )

    answer_scope: Literal["record", "crop"] = Field(
        default="record",
        description="'record' means the answer concerns one matched pest record. 'crop' means "
        "the pest could not be matched (for example a Hindi pest name against an English-only "
        "index), so every record for that crop is listed instead of guessing one.",
    )
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    safety_disclosures: list[SafetyDisclosure] = Field(default_factory=list)
    advisory_status: Optional[AdvisoryStatus] = None

    rule_findings: list[dict] = Field(
        default_factory=list,
        description="Phase 7 rule findings in the answer language. Empty when the decision gate "
        "refused the query before any record was selected (see `rule_trace`).",
    )
    decision: Optional[str] = Field(
        default=None,
        description="Phase 7 decision class: ACTIONABLE_RECOMMENDATION, EDUCATIONAL_INFORMATION, "
        "SAFETY_REFUSAL, REGULATORY_VERIFICATION_REQUIRED, ESCALATION_REQUIRED or "
        "CLARIFICATION_REQUIRED. Null only when no rule ran.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Fields that are absent and required for an actionable recommendation "
        "(e.g. 'phi', 'rei', 'regulatory_approval'). Populated from rule findings, never guessed.",
    )
    rule_trace: dict = Field(
        default_factory=dict,
        description="Which rules ran, which triggered, and the thresholds used. Always present, "
        "so 'no rule fired' can be told apart from 'no rule ran'.",
    )

    confidence: float = Field(ge=0.0, le=1.0)
    confidence_label: ConfidenceLabel
    confidence_components: dict = Field(default_factory=dict)

    classification: dict = Field(
        description="Crop / task / safety context the retrieval was conditioned on."
    )
    generation_mode: Literal["extractive"] = "extractive"
    model_versions: dict = Field(default_factory=dict)

    usage_policy: dict = Field(
        default_factory=lambda: {
            "is_pesticide_recommendation": False,
            "is_regulatory_approval": False,
            "may_state_dosage_as_authoritative": False,
            "must_show_citations": True,
            "educational_only": True,
        }
    )


class RagStatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    rule_engine: dict = Field(
        default_factory=dict,
        description="Phase 7 rule declarations and thresholds, so /rag/status reports the gate "
        "that the answers actually passed through.",
    )
    vector_backend: str
    embedding_model: str
    indexed_chunks: int
    repository_backend: Optional[str]
    classifier_version: str
    generation_mode: str = "extractive"
    thresholds: dict
