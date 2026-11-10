"""
Phase 7 — request/response schemas for the standalone rule surface.

`POST /rules/evaluate` exists so the rule engine can be exercised without
running retrieval. That matters for two reasons: the rules are graded
independently of the RAG pipeline, and a reviewer can ask "what does the engine
say about wheat termite?" and get the verdict rather than a composed answer.

The confidence inputs are optional and the response says so. When they are
absent the confidence rule reports `not_evaluated` with a reason — a rule that
did not run is never presented as a rule that passed.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuleEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=1, max_length=64, description="Classified or asserted crop label.")
    target_pest: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional pest name. When given, RequireApprovedPair checks that a record "
        "for that crop actually targets it.",
    )
    record_ids: Optional[list[str]] = Field(
        default=None,
        max_length=10,
        description="Explicit records to evaluate. Omit to use every record for the crop.",
    )
    classifier_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    retrieval_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    language: Literal["en", "hi"] = "en"


class RuleFindingOut(BaseModel):
    rule_id: str
    code: str
    severity: str
    action: str
    message: str
    detail: dict = Field(default_factory=dict)


class RuleEvaluationOut(BaseModel):
    rule_id: str
    name: str
    trigger: str
    action: str
    severity: str
    status: str
    note: Optional[str] = None
    findings: list[RuleFindingOut] = Field(default_factory=list)


class RuleEvaluateResponse(BaseModel):
    crop: str
    target_pest: Optional[str] = None
    records_evaluated: list[str] = Field(default_factory=list)
    blocked: bool
    blocking_action: Optional[str] = None
    actionability: Literal["ACTIONABLE_WITH_EVIDENCE", "EDUCATIONAL_ONLY"]
    decision: str = Field(
        default="EDUCATIONAL_INFORMATION",
        description="ACTIONABLE_RECOMMENDATION, EDUCATIONAL_INFORMATION, SAFETY_REFUSAL, "
        "REGULATORY_VERIFICATION_REQUIRED, ESCALATION_REQUIRED or CLARIFICATION_REQUIRED.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Fields absent and required for an actionable recommendation.",
    )
    message: str = Field(
        default="", description="Fixed escalation text when blocked; empty otherwise."
    )
    evaluations: list[RuleEvaluationOut] = Field(default_factory=list)
    trace: dict = Field(default_factory=dict)


class RuleStatusResponse(BaseModel):
    engine: str
    generation_involvement: str
    rules: list[dict]
    block_precedence: list[str]
    thresholds: dict
    knowledge_base: dict = Field(
        default_factory=dict,
        description="How many records can currently be actionable, and why the rest cannot.",
    )
