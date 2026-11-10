"""
Phase 7 — Rule-Based Safety Engine (blueprint Module E).

    from app.rules import RuleContext, get_rule_engine

    verdict = get_rule_engine().evaluate(RuleContext(records=(record,), ...))
    if verdict.blocked:
        ...  # escalate with escalation_message(verdict.blocking_action, "en")

The engine is deterministic: no LLM, no randomness, no wall-clock reading outside
`RuleContext.today`. Given the same context it returns the same verdict, which is
what makes the per-rule test cases in `backend/tests/test_phase7_rules.py`
meaningful rather than anecdotal.
"""
from app.rules.context import (
    SAFETY_FIELD_NAMES,
    RuleContext,
    first_number,
    is_fully_published,
    missing_safety_fields,
    normalize_pest,
    safety_profile,
)
from app.rules.engine import (
    BLOCK_PRECEDENCE,
    RuleEngine,
    RuleEngineInconsistency,
    assert_consistency,
    get_rule_engine,
    rule_engine_status,
)
from app.rules.escalation import ESCALATION_MESSAGES, escalation_message
from app.rules.rules import (
    DEFAULT_RULES,
    ConfidenceGate,
    ContradictionCheck,
    RequireApprovedPair,
    RequireSafetyFields,
    Rule,
    StaleSourceCheck,
)
from app.rules.verification import (
    DEFAULT_EVIDENCE_PATH,
    REGISTRY_CIBRC,
    RegulatoryEvidence,
    RegulatoryEvidenceError,
    evidence_ids,
    is_verified,
    load_regulatory_evidence,
)
from app.rules.schemas import (
    DECISIONS,
    ESCALATION_ACTIONS,
    RULE_IDS,
    AdvisoryStatus,
    Decision,
    EscalationAction,
    RuleEvaluation,
    RuleFinding,
    RuleStatus,
    RuleVerdict,
)

__all__ = [
    "AdvisoryStatus",
    "DEFAULT_EVIDENCE_PATH",
    "REGISTRY_CIBRC",
    "RegulatoryEvidence",
    "RegulatoryEvidenceError",
    "evidence_ids",
    "is_verified",
    "load_regulatory_evidence",
    "DECISIONS",
    "Decision",
    "BLOCK_PRECEDENCE",
    "ConfidenceGate",
    "ContradictionCheck",
    "DEFAULT_RULES",
    "ESCALATION_ACTIONS",
    "ESCALATION_MESSAGES",
    "EscalationAction",
    "RULE_IDS",
    "RequireApprovedPair",
    "RequireSafetyFields",
    "Rule",
    "RuleContext",
    "RuleEngine",
    "RuleEngineInconsistency",
    "RuleEvaluation",
    "RuleFinding",
    "RuleStatus",
    "RuleVerdict",
    "SAFETY_FIELD_NAMES",
    "StaleSourceCheck",
    "assert_consistency",
    "escalation_message",
    "first_number",
    "get_rule_engine",
    "is_fully_published",
    "missing_safety_fields",
    "normalize_pest",
    "rule_engine_status",
    "safety_profile",
]
