"""
Phase 7 — rule engine contract.

The rule engine is a deterministic gate that sits between retrieval and answer
composition. The blueprint (§12) names five rules and three escalation actions;
this module is the type-level version of that table, so a rule cannot silently
invent a sixth action or report a severity the rest of the system does not know.

Design notes that matter for review:

* **No rule can "partially" block.** A rule either passes, triggers, or is
  explicitly `not_evaluated` (with a reason). There is no silent skip, because a
  rule that quietly did not run is indistinguishable from a rule that passed.
* **Severity is part of the rule, not the finding.** `RequireSafetyFields` does
  not block the answer — an educational answer about a source-transcribed
  recommendation is allowed — but it does block `ACTIONABLE_WITH_EVIDENCE`.
  Encoding that as a rule-level severity keeps every finding of that rule
  consistent, instead of leaving each call site to decide.
* **Messages are fixed templates in both languages**, held here as data rather
  than generated at request time. Blueprint §13 requires the escalation text to
  be pre-translated so a translation step can never alter a safety verdict.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# One definition, two forms: the Literal used by Pydantic, and a runtime tuple so
# tests and callers can assert membership without duplicating the list.
RULE_IDS = (
    "R1_REQUIRE_APPROVED_PAIR",
    "R2_REQUIRE_SAFETY_FIELDS",
    "R3_CONTRADICTION_CHECK",
    "R4_CONFIDENCE_GATE",
    "R5_STALE_SOURCE_CHECK",
)
RuleId = Literal[
    "R1_REQUIRE_APPROVED_PAIR",
    "R2_REQUIRE_SAFETY_FIELDS",
    "R3_CONTRADICTION_CHECK",
    "R4_CONFIDENCE_GATE",
    "R5_STALE_SOURCE_CHECK",
]

ESCALATION_ACTIONS = (
    "ESCALATE_MISSING_INFO",
    "ESCALATE_CONTRADICTION",
    "ESCALATE_LOW_CONFIDENCE",
    "WARN_VERIFY_CURRENCY",
)
EscalationAction = Literal[
    "ESCALATE_MISSING_INFO",
    "ESCALATE_CONTRADICTION",
    "ESCALATE_LOW_CONFIDENCE",
    "WARN_VERIFY_CURRENCY",
]

# block                     -> the answer is refused entirely
# restrict_actionability    -> the answer may be shown, but never as actionable
# warn                      -> attached to the answer, never blocks on its own
RuleSeverity = Literal["block", "restrict_actionability", "warn"]

RuleStatus = Literal["passed", "triggered", "not_evaluated"]

AdvisoryStatus = Literal["ACTIONABLE_WITH_EVIDENCE", "EDUCATIONAL_ONLY"]

# Phase 7 requirement: the five decision classes the system must keep apart.
# `actionability` alone cannot do this — it is a two-valued safety bit, while
# "the sources disagree" and "nothing exists for this pest" are different answers
# that both read as `blocked`. The decision is derived from the findings, in one
# place, so no caller has to re-derive it from booleans.
DECISIONS = (
    "ACTIONABLE_RECOMMENDATION",
    "EDUCATIONAL_INFORMATION",
    "SAFETY_REFUSAL",
    "REGULATORY_VERIFICATION_REQUIRED",
    "ESCALATION_REQUIRED",
    "CLARIFICATION_REQUIRED",
)
Decision = Literal[
    "ACTIONABLE_RECOMMENDATION",
    "EDUCATIONAL_INFORMATION",
    "SAFETY_REFUSAL",
    "REGULATORY_VERIFICATION_REQUIRED",
    "ESCALATION_REQUIRED",
    "CLARIFICATION_REQUIRED",
]


class RuleFinding(BaseModel):
    """One concrete reason a rule fired. Never a generated sentence."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(
        description="Stable machine-readable reason, e.g. 'phi_not_published'. "
        "Tests and the UI key off this, not off the message text."
    )
    message_en: str
    message_hi: str
    detail: dict = Field(
        default_factory=dict,
        description="Structured evidence for the finding (record ids, field names, "
        "values compared). Never contains an invented value.",
    )

    def message(self, language: str) -> str:
        return self.message_hi if language == "hi" else self.message_en


class RuleEvaluation(BaseModel):
    """The result of running one rule once."""

    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    name: str
    trigger: str = Field(description="The blueprint §12 trigger condition, verbatim in spirit.")
    action: EscalationAction
    severity: RuleSeverity
    status: RuleStatus
    findings: list[RuleFinding] = Field(default_factory=list)
    note: Optional[str] = Field(
        default=None,
        description="Why the rule did not evaluate, when status is 'not_evaluated'.",
    )

    @property
    def triggered(self) -> bool:
        return self.status == "triggered"


class RuleVerdict(BaseModel):
    """What the engine concluded. This is the object the pipeline obeys."""

    model_config = ConfigDict(extra="forbid")

    blocked: bool
    blocking_action: Optional[EscalationAction] = None
    actionability: AdvisoryStatus
    evaluations: list[RuleEvaluation] = Field(default_factory=list)
    warnings: list[RuleFinding] = Field(
        default_factory=list, description="Non-blocking findings, never a refusal on their own."
    )
    decision: Decision = Field(
        default="EDUCATIONAL_INFORMATION",
        description="The decision class (Phase 7 requirement 5), derived from the findings by "
        "engine._decide(). ACTIONABLE_RECOMMENDATION requires complete PHI/REI/PPE *and* a "
        "recorded regulatory verification; neither is assumed.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Field names that are absent and required for an actionable recommendation, "
        "e.g. ['phi', 'rei', 'regulatory_approval']. Never inferred from a message string.",
    )
    trace: dict = Field(
        default_factory=dict,
        description="Counts and thresholds used for this evaluation, for the audit log.",
    )

    @property
    def findings(self) -> list[RuleFinding]:
        return [f for e in self.evaluations for f in e.findings]

    def rule_findings(self, language: str = "en") -> list[dict]:
        """
        Flatten to the shape the HTTP response carries.

        Messages are rendered in one language here because the response has a
        single `answer_language`; the other language stays in the evaluation
        object for logs and tests.
        """
        out: list[dict] = []
        for evaluation in self.evaluations:
            for finding in evaluation.findings:
                out.append(
                    {
                        "rule_id": evaluation.rule_id,
                        "code": finding.code,
                        "severity": evaluation.severity,
                        "action": evaluation.action,
                        "message": finding.message(language),
                        "detail": finding.detail,
                    }
                )
        return out
