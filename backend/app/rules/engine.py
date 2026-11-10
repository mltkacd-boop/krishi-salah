"""
Phase 7 — the one place a verdict is computed.

    RuleContext -> [R1, R2, R3, R4, R5] -> RuleVerdict

Two properties this module is responsible for, and nothing else:

1. **One blocking action, chosen by a fixed precedence.** Several rules can fire
   on the same query. The verdict reports every finding but exactly one
   `blocking_action`, selected by `BLOCK_PRECEDENCE`, so the escalation text is
   deterministic for a given input rather than dependent on rule ordering in a
   list.
2. **Actionability is a separate axis from refusal.** A response can be
   answered, cited and educational-only at the same time; that is the normal
   case in this pilot. Collapsing the two into one boolean is what would let an
   incomplete-safety record be rendered as an actionable recommendation.

The engine also enforces agreement between the rule engine's own actionability
computation and `ApprovedUse.advisory_status`. This mirrors the Phase 5 decision
to implement the safety gate twice (Python + SQL) and prove the two agree: a
single implementation would be a single point of failure for the project's core
safety claim. Disagreement raises `RuleEngineInconsistency`, which is
deliberately fail-closed — a request that hits it returns no answer at all
rather than an answer whose safety status is ambiguous.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from app.knowledge_base.models import ApprovedUse
from app.rules.context import RuleContext, is_fully_published, missing_safety_fields
from app.rules.rules import DEFAULT_RULES, ContradictionCheck, ConfidenceGate, Rule, StaleSourceCheck
from app.rules.schemas import RULE_IDS, RuleEvaluation, RuleFinding, RuleVerdict
from app.rules.verification import evidence_ids

# Why this order: missing-pair is the strongest statement (there is nothing to
# discuss), then a contradiction (the sources disagree), then no confidence (we
# cannot tell what is being asked). Actionability restriction never appears here
# because it cannot block an answer.
BLOCK_PRECEDENCE: tuple[str, ...] = (
    "R1_REQUIRE_APPROVED_PAIR",
    "R3_CONTRADICTION_CHECK",
    "R4_CONFIDENCE_GATE",
    "R2_REQUIRE_SAFETY_FIELDS",
    "R5_STALE_SOURCE_CHECK",
)


class RuleEngineInconsistency(RuntimeError):
    """The rule engine and the Pydantic model disagree about actionability."""


# Findings that are satisfied only by evidence this project has never obtained.
_REGULATORY_CODES = frozenset({"regulatory_approval_not_verified"})


def _decide(
    evaluations: Sequence[RuleEvaluation],
    blocking: Optional[RuleEvaluation],
    actionability: str,
) -> str:
    """
    Map findings to exactly one decision class.

    Derived from the findings rather than from severity, because two rules can
    share a severity and still mean different things to the person reading the
    answer. Being a pure function of the evaluation list, it is assertable
    case by case and cannot drift from the rules it summarises.
    """
    codes = {f.code for e in evaluations if e.status == "triggered" for f in e.findings}

    if blocking is not None:
        # Decided by the blocking rule, not by every finding on the request. A
        # crop-mismatch refusal also carries R2 findings (the mismatched record
        # still has an incomplete safety profile), so aggregating all findings
        # would report "unsafe to act on" when the real reason is "nothing here
        # answers this question".
        if blocking.rule_id == "R4_CONFIDENCE_GATE":
            return "CLARIFICATION_REQUIRED"
        if blocking.rule_id == "R1_REQUIRE_APPROVED_PAIR":
            return "ESCALATION_REQUIRED"
        return "SAFETY_REFUSAL"

    if actionability == "ACTIONABLE_WITH_EVIDENCE":
        return "ACTIONABLE_RECOMMENDATION"

    # Nothing blocked, but something restricted actionability. If the only
    # restriction is the missing registration check, say that specifically; the
    # user's next step is a registry/label check, not "read this as education".
    if codes and codes <= _REGULATORY_CODES:
        return "REGULATORY_VERIFICATION_REQUIRED"
    return "EDUCATIONAL_INFORMATION"


def _missing_information(evaluations: Sequence[RuleEvaluation]) -> list[str]:
    """Every field named as missing or unverified, deduplicated and ordered."""
    ordered: list[str] = []
    for evaluation in evaluations:
        if evaluation.status != "triggered":
            continue
        for finding in evaluation.findings:
            for field in finding.detail.get("missing_fields", []):
                if field not in ordered:
                    ordered.append(field)
    return ordered


def assert_consistency(records: Sequence[ApprovedUse]) -> None:
    """
    Prove `is_fully_published` and `ApprovedUse.advisory_status` agree.

    Called on every evaluation, so a future change to either definition cannot
    make the served safety status diverge from the audited one without failing
    loudly.
    """
    mismatched = [
        record.approved_use_id
        for record in records
        if is_fully_published(record)
        != (record.advisory_status == "ACTIONABLE_WITH_EVIDENCE")
    ]
    if mismatched:
        raise RuleEngineInconsistency(
            "rule-engine actionability and ApprovedUse.advisory_status disagree for: "
            + ", ".join(sorted(mismatched))
        )


class RuleEngine:
    """Deterministic evaluation of the blueprint §12 rules."""

    def __init__(self, rules: Iterable[Rule] = DEFAULT_RULES) -> None:
        self.rules: tuple[Rule, ...] = tuple(rules)

    # -- configuration -----------------------------------------------------
    def thresholds(self) -> dict:
        out: dict = {}
        for rule in self.rules:
            if isinstance(rule, ContradictionCheck):
                out["contradiction_tolerance_days"] = rule.tolerance_days
            elif isinstance(rule, ConfidenceGate):
                out["min_classifier_confidence"] = rule.min_classifier_confidence
                out["min_retrieval_confidence"] = rule.min_retrieval_confidence
            elif isinstance(rule, StaleSourceCheck):
                out["source_freshness_years"] = rule.freshness_years
        return out

    def registry(self) -> list[dict]:
        """Rule declarations, for `/rules/status` and the written report."""
        return [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "trigger": rule.trigger,
                "action": rule.action,
                "severity": rule.severity,
            }
            for rule in self.rules
        ]

    # -- evaluation --------------------------------------------------------
    def evaluate(self, ctx: RuleContext) -> RuleVerdict:
        declared = {rule.rule_id for rule in self.rules}
        if declared != set(RULE_IDS) or len(self.rules) != len(RULE_IDS):
            raise RuleEngineInconsistency(
                f"engine rules {sorted(declared)} do not match the declared rule set "
                f"{sorted(RULE_IDS)} — a rule that was silently dropped or duplicated would make "
                f"every verdict incomplete"
            )
        assert_consistency(ctx.records)

        evaluations = [rule.evaluate(ctx) for rule in self.rules]
        by_id = {evaluation.rule_id: evaluation for evaluation in evaluations}

        blocking = self._first_blocking(by_id)
        restricted = [
            e for e in evaluations
            if e.status == "triggered" and e.severity == "restrict_actionability"
        ]
        warnings: list[RuleFinding] = [
            finding
            for evaluation in evaluations
            if evaluation.status == "triggered" and evaluation.severity == "warn"
            for finding in evaluation.findings
        ]

        actionability = (
            "ACTIONABLE_WITH_EVIDENCE"
            if blocking is None and not restricted
            else "EDUCATIONAL_ONLY"
        )
        decision = _decide(evaluations, blocking, actionability)
        missing_information = _missing_information(evaluations)

        return RuleVerdict(
            blocked=blocking is not None,
            blocking_action=blocking.action if blocking else None,
            actionability=actionability,
            decision=decision,
            missing_information=missing_information,
            evaluations=evaluations,
            warnings=warnings,
            trace={
                "engine": "deterministic_rules",
                "rules_run": [e.rule_id for e in evaluations],
                "triggered": [e.rule_id for e in evaluations if e.status == "triggered"],
                "not_evaluated": [
                    {"rule_id": e.rule_id, "reason": e.note}
                    for e in evaluations
                    if e.status == "not_evaluated"
                ],
                "blocking_rule": blocking.rule_id if blocking else None,
                "blocking_action": blocking.action if blocking else None,
                "actionability": actionability,
                "decision": decision,
                "missing_information": missing_information,
                "records_evaluated": [r.approved_use_id for r in ctx.records],
                "missing_safety_fields": {
                    r.approved_use_id: missing_safety_fields(r) for r in ctx.records
                },
                # Evidence provenance, so an audit can see whether the gate was
                # opened by a real manifest and which records it covered.
                "regulatory_evidence_source": ctx.regulatory_evidence_source,
                "regulatory_evidence_records": evidence_ids(ctx.regulatory_verification),
                "thresholds": self.thresholds(),
                "evaluated_on": ctx.today.isoformat(),
            },
        )

    def _first_blocking(self, by_id: dict[str, RuleEvaluation]) -> RuleEvaluation | None:
        for rule_id in BLOCK_PRECEDENCE:
            evaluation = by_id.get(rule_id)
            if evaluation and evaluation.status == "triggered" and evaluation.severity == "block":
                return evaluation
        return None


_engine: RuleEngine | None = None


def get_rule_engine() -> RuleEngine:
    global _engine
    if _engine is None:
        _engine = RuleEngine()
    return _engine


def rule_engine_status() -> dict:
    engine = get_rule_engine()
    return {
        "engine": "deterministic_rules",
        "generation_involvement": "none",
        "rules": engine.registry(),
        "block_precedence": list(BLOCK_PRECEDENCE),
        "thresholds": engine.thresholds(),
    }
