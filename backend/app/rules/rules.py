"""
Phase 7 — the five rules from blueprint §12, as deterministic Python classes.

Each rule is a pure function of `RuleContext`. No rule reads the wall clock
except through `ctx.today`, no rule opens a database, and no rule produces a
sentence from anything but the fixed bilingual templates below. That is what
makes the safety behaviour testable case by case ("missing PHI -> must
restrict actionability") instead of assertable only end to end.

WHAT EACH RULE IS ALLOWED TO DO
-------------------------------
`RequireApprovedPair`, `ContradictionCheck` and `ConfidenceGate` have block
severity: they can stop an answer. `RequireSafetyFields` has
`restrict_actionability` severity, because the project's approved position
(DEC-010) is that an incomplete-safety record may still be *explained* — it may
never be presented as an actionable dose. `StaleSourceCheck` only warns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from app.knowledge_base.models import ApprovedUse
from app.rules.context import (
    SAFETY_FIELD_NAMES,
    RuleContext,
    first_number,
    is_fully_published,
    missing_safety_fields,
    normalize_pest,
    safety_profile,
)
from app.rules.verification import is_verified
from app.rules.schemas import (
    EscalationAction,
    RuleEvaluation,
    RuleFinding,
    RuleId,
    RuleSeverity,
)


@dataclass(frozen=True)
class Rule:
    """Base class: a declaration plus an `evaluate` that returns findings."""

    rule_id: RuleId
    name: str
    trigger: str
    action: EscalationAction
    severity: RuleSeverity

    def evaluate(self, ctx: RuleContext) -> RuleEvaluation:
        findings, note = self.check(ctx)
        if note is not None:
            status = "not_evaluated"
        else:
            status = "triggered" if findings else "passed"
        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            trigger=self.trigger,
            action=self.action,
            severity=self.severity,
            status=status,
            findings=findings,
            note=note,
        )

    def check(self, ctx: RuleContext) -> tuple[list[RuleFinding], Optional[str]]:
        """Return (findings, note). A non-None note means the rule did not run."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# R1
# ---------------------------------------------------------------------------
class RequireApprovedPair(Rule):
    """
    No approved-use pair (crop + target), no answer.

    This is not a duplicate of the Phase 6 decision gate. The gate decides from
    *retrieved chunks*; this rule re-checks the *records actually selected for
    the answer*, which is the last moment before text is composed. It catches
    the cases the gate cannot: a record that vanished from the repository
    between retrieval and composition, a record whose crop disagrees with the
    crop the classifier named, and (on the standalone surface) a pest that no
    record for that crop covers.
    """

    def __init__(self) -> None:
        super().__init__(
            rule_id="R1_REQUIRE_APPROVED_PAIR",
            name="RequireApprovedPair",
            trigger="No approved_use row exists for the classified crop and target.",
            action="ESCALATE_MISSING_INFO",
            severity="block",
        )

    def check(self, ctx: RuleContext) -> tuple[list[RuleFinding], Optional[str]]:
        if ctx.crop_label is None and not ctx.records:
            return [], "no classified crop and no selected record"

        findings: list[RuleFinding] = []

        if not ctx.records:
            findings.append(RuleFinding(
                code="no_record_for_crop_target",
                message_en="No record for this crop and target exists in this knowledge base, so "
                           "there is nothing to advise from. Approving or extrapolating one would "
                           "be a guess.",
                message_hi="इस फसल और लक्षित कीट के लिए इस ज्ञान-आधार में कोई रिकॉर्ड नहीं है, "
                           "इसलिए सलाह देने का आधार नहीं है। अनुमान लगाना सुरक्षित नहीं होगा।",
                detail={"crop": ctx.crop_label, "target_pest": ctx.target_pest},
            ))
            return findings, None

        for record in ctx.records:
            canonical = ctx.all_records.get(record.approved_use_id)
            if canonical is None:
                findings.append(RuleFinding(
                    code="record_missing_from_knowledge_base",
                    message_en="A record selected for this answer is no longer present in the "
                               "knowledge base, so its statement cannot be verified.",
                    message_hi="इस उत्तर के लिए चुना गया रिकॉर्ड अब ज्ञान-आधार में नहीं है, "
                               "इसलिए उसके कथन की पुष्टि नहीं हो सकती।",
                    detail={"record_id": record.approved_use_id},
                ))
                continue
            if ctx.crop_label and canonical.crop_id != ctx.crop_label:
                findings.append(RuleFinding(
                    code="record_crop_mismatch",
                    message_en="The selected record belongs to a different crop than the one "
                               "recognised in the question, so it cannot answer it.",
                    message_hi="चुना गया रिकॉर्ड प्रश्न में पहचानी गई फसल से भिन्न फसल का है, "
                               "इसलिए यह उत्तर नहीं दे सकता।",
                    detail={
                        "record_id": canonical.approved_use_id,
                        "record_crop": canonical.crop_id,
                        "classified_crop": ctx.crop_label,
                    },
                ))

        if ctx.target_pest and not findings:
            pest_tokens = set(normalize_pest(ctx.target_pest).split())
            covered = any(
                pest_tokens <= set(normalize_pest(r.target_pest_common_name).split())
                for r in ctx.records
            )
            if not covered:
                findings.append(RuleFinding(
                    code="target_pest_not_covered",
                    message_en="This knowledge base has no record for that pest on that crop.",
                    message_hi="इस ज्ञान-आधार में उस फसल पर उस कीट का कोई रिकॉर्ड नहीं है।",
                    detail={"target_pest": ctx.target_pest, "crop": ctx.crop_label},
                ))

        return findings, None


# ---------------------------------------------------------------------------
# R2
# ---------------------------------------------------------------------------
class RequireSafetyFields(Rule):
    """
    Everything an actionable recommendation needs must be published and traced.

    Three distinct gaps are checked per record, in this order, because they fail
    for different reasons and a reader needs to tell them apart:

    1. **Safety profile** — PHI, REI, PPE and dosage for every chemical
       intervention. Every intervention is checked separately: PHI and REI attach
       to a product+label, so a record offering four interchangeable products is
       only actionable if all four are complete.
    2. **Regulatory verification** — whether a CIB&RC registration check has been
       recorded for that record (`RuleContext.regulatory_verification`). The
       knowledge base's `verification_status` value is
       `VERIFIED_SOURCE_RECOMMENDATION`, which its own docstring defines as "not
       cross-checked against the live CIB&RC registry". Reporting a
       source-transcribed dose as an approved one would be exactly the
       source-verification-vs-regulatory-approval confusion this project exists
       to avoid, so the absence of a recorded check blocks actionability.
    3. **Source verification** — a record whose `verification_status` is not
       `VERIFIED_SOURCE_RECOMMENDATION` has not even been traced to a fetched
       page.

    Severity is `restrict_actionability`, not `block`: the answer may still be
    shown as education, but the whole response is forced to `EDUCATIONAL_ONLY`.
    """

    def __init__(self) -> None:
        super().__init__(
            rule_id="R2_REQUIRE_SAFETY_FIELDS",
            name="RequireSafetyFields",
            trigger="PHI, REI, PPE, dosage, label/traceability or regulatory approval is missing, "
                    "unpublished or unverified for a chemical intervention on the matched record.",
            action="ESCALATE_MISSING_INFO",
            severity="restrict_actionability",
        )

    def check(self, ctx: RuleContext) -> tuple[list[RuleFinding], Optional[str]]:
        if not ctx.records:
            return [], "no record selected, so there is no safety profile to check"

        findings: list[RuleFinding] = []
        for record in ctx.records:
            missing = missing_safety_fields(record)
            if missing == ["chemical_intervention"]:
                findings.append(RuleFinding(
                    code="no_chemical_intervention",
                    message_en="This record lists no chemical measure, so it carries no pesticide "
                               "safety profile and cannot be presented as a pesticide "
                               "recommendation.",
                    message_hi="इस रिकॉर्ड में कोई रासायनिक उपाय नहीं है, इसलिए इसमें कीटनाशक "
                               "सुरक्षा विवरण नहीं है और इसे कीटनाशक सिफ़ारिश के रूप में नहीं "
                               "दिखाया जा सकता।",
                    detail={"record_id": record.approved_use_id},
                ))
            elif missing:
                findings.append(RuleFinding(
                    code="safety_fields_not_published",
                    message_en="The source does not publish a complete PHI, REI and PPE profile for "
                               "every chemical option in this record, so it can be shown as "
                               "educational information only — never as an actionable dose, waiting "
                               "period or protective-equipment instruction.",
                    message_hi="स्रोत इस रिकॉर्ड के हर रासायनिक विकल्प के लिए पूरा PHI, REI और PPE "
                               "विवरण नहीं देता, इसलिए इसे केवल शैक्षिक जानकारी के रूप में दिखाया "
                               "जा सकता है — क्रियान्वयन योग्य मात्रा, प्रतीक्षा अवधि या सुरक्षा "
                               "उपकरण निर्देश के रूप में कभी नहीं।",
                    detail={
                        "record_id": record.approved_use_id,
                        "missing_fields": missing,
                        "chemical_interventions": len(safety_profile(record)),
                    },
                ))

            if not is_verified(
                ctx.regulatory_verification, record.approved_use_id, today=ctx.today
            ):
                findings.append(RuleFinding(
                    code="regulatory_approval_not_verified",
                    message_en="No current CIB&RC registration check is recorded for the product or "
                               "label behind this advice. What is published here is a source-"
                               "transcribed recommendation, not a regulatory approval, so it is "
                               "educational information only. Verify the registration number on "
                               "the product label before buying or spraying anything.",
                    message_hi="इस सलाह के पीछे के उत्पाद या लेबल के लिए CIB&RC पंजीकरण की कोई "
                               "वर्तमान जाँच दर्ज नहीं है। यहाँ जो प्रकाशित है वह स्रोत से उद्धृत "
                               "सिफ़ारिश है, नियामक अनुमोदन नहीं, इसलिए यह केवल शैक्षिक जानकारी "
                               "है। कुछ भी खरीदने या छिड़कने से पहले उत्पाद के लेबल पर पंजीकरण "
                               "संख्या की पुष्टि करें।",
                    detail={
                        "record_id": record.approved_use_id,
                        "missing_fields": ["regulatory_approval"],
                        "registry_checked": False,
                    },
                ))

            if record.verification_status != "VERIFIED_SOURCE_RECOMMENDATION":
                findings.append(RuleFinding(
                    code="record_not_source_verified",
                    message_en="This record is a draft that has not been traced to a fetched "
                               "source page, so none of its statements can be relied on yet.",
                    message_hi="यह रिकॉर्ड एक प्रारूप है जिसे किसी प्राप्त स्रोत पृष्ठ से नहीं "
                               "जोड़ा गया, इसलिए इसके किसी भी कथन पर अभी भरोसा नहीं किया जा "
                               "सकता।",
                    detail={
                        "record_id": record.approved_use_id,
                        "verification_status": record.verification_status,
                        "missing_fields": ["source_verification"],
                    },
                ))
        return findings, None


# ---------------------------------------------------------------------------
# R3
# ---------------------------------------------------------------------------
class ContradictionCheck(Rule):
    """
    Two sources disagreeing on a safety-critical number is an escalation, never
    a choice.

    Only leading numbers of a PUBLISHED PHI/REI value are compared, only between
    records that target the same crop and the same normalised pest name, and
    only across distinct sources (the blueprint's "two retrieved chunks from
    different sources"). A tolerance exists because a day-boundary difference is
    not a contradiction; the default is zero, i.e. any difference escalates.

    The compared numbers are deliberately kept out of the finding's `detail`.
    Emitting "7 vs 21 days" inside a refusal would hand the user the very value
    the refusal exists to withhold.
    """

    def __init__(self, tolerance_days: float = 0.0) -> None:
        self.tolerance_days = tolerance_days
        super().__init__(
            rule_id="R3_CONTRADICTION_CHECK",
            name="ContradictionCheck",
            trigger="Two retrieved chunks from different sources disagree on a safety-critical "
                    "numeric field beyond a tolerance.",
            action="ESCALATE_CONTRADICTION",
            severity="block",
        )

    def check(self, ctx: RuleContext) -> tuple[list[RuleFinding], Optional[str]]:
        if not ctx.records:
            return [], "no record selected, so there is nothing to compare"

        findings = self._within_record(ctx) + self._across_records(ctx)
        return findings, None

    def _within_record(self, ctx: RuleContext) -> list[RuleFinding]:
        """
        One record, two published values for the same field: the record
        contradicts itself, so its profile cannot be trusted either way.
        """
        findings: list[RuleFinding] = []
        for record in ctx.records:
            for field in ("phi", "rei"):
                published: list[float] = []
                for intervention in record.interventions:
                    restrictions = intervention.safety_restrictions
                    if restrictions is None:
                        continue
                    declared = getattr(restrictions, field)
                    if declared.status != "PUBLISHED":
                        continue
                    number = first_number(declared.value)
                    if number is not None:
                        published.append(number)
                record_level = getattr(record.safety_restrictions, field)
                if record_level.status == "PUBLISHED":
                    number = first_number(record_level.value)
                    if number is not None:
                        published.append(number)
                if len(published) > 1 and max(published) - min(published) > self.tolerance_days:
                    findings.append(RuleFinding(
                        code=f"{field}_conflicts_within_record",
                        message_en="This record carries two different safety values for the same "
                                   "chemical measure, so its safety profile is internally "
                                   "inconsistent and nothing is recommended from it.",
                        message_hi="इस रिकॉर्ड में एक ही रासायनिक उपाय के लिए दो भिन्न सुरक्षा "
                                   "मान हैं, इसलिए इसका सुरक्षा विवरण परस्पर विरोधी है और इससे "
                                   "कोई सिफ़ारिश नहीं दी जा सकती।",
                        detail={"record_id": record.approved_use_id, "field": field},
                    ))
        return findings

    def _across_records(self, ctx: RuleContext) -> list[RuleFinding]:
        groups: dict[tuple[str, str], list[ApprovedUse]] = {}
        for record in ctx.records:
            key = (record.crop_id, normalize_pest(record.target_pest_common_name))
            groups.setdefault(key, []).append(record)

        findings: list[RuleFinding] = []
        for (crop_id, pest), group in sorted(groups.items()):
            if len({r.source_id for r in group}) < 2:
                continue
            for field in ("phi", "rei"):
                values = []
                for record in group:
                    declared = getattr(record.safety_restrictions, field)
                    if declared.status != "PUBLISHED":
                        continue
                    number = first_number(declared.value)
                    if number is not None:
                        values.append((record.approved_use_id, record.source_id, number))
                if len({v[1] for v in values}) < 2:
                    continue
                numbers = [v[2] for v in values]
                if max(numbers) - min(numbers) > self.tolerance_days:
                    findings.append(RuleFinding(
                        code=f"{field}_conflicts_across_sources",
                        message_en="Two sources state different safety values for the same crop "
                                   "and target. Choosing one, or averaging them, would be an "
                                   "invention, so no value is given.",
                        message_hi="एक ही फसल और लक्ष्य के लिए दो स्रोत भिन्न सुरक्षा मान बताते "
                                   "हैं। किसी एक को चुनना या औसत निकालना अनुमान होगा, इसलिए कोई "
                                   "मान नहीं दिया जा रहा।",
                        detail={
                            "crop": crop_id,
                            "pest": pest,
                            "field": field,
                            "records": [v[0] for v in values],
                            "sources": [v[1] for v in values],
                        },
                    ))
        return findings


# ---------------------------------------------------------------------------
# R4
# ---------------------------------------------------------------------------
class ConfidenceGate(Rule):
    """
    Refuse when *every available* signal is below its floor.

    The blueprint says "classifier confidence < threshold OR retrieval
    similarity < threshold". That OR is wrong for this system and the Phase 6
    measurements show why: with the lexical embedder the in-scope Hindi query
    `धान का तना छेदक` scores 0.111 while the out-of-scope `what is the mandi
    price of rice today` scores 0.311. A similarity floor would refuse the
    right question and accept the wrong one.

    So the gate blocks only when no signal supports an answer at all (the
    classifier is unsure AND retrieval found nothing similar). A single low
    signal produces a warning instead, which keeps the measured Hindi behaviour
    intact. When only one signal is supplied — the standalone `/rules/evaluate`
    surface — that signal decides, because there is nothing to corroborate it.
    """

    def __init__(
        self,
        min_classifier_confidence: float = 0.40,
        min_retrieval_confidence: float = 0.10,
    ) -> None:
        self.min_classifier_confidence = min_classifier_confidence
        self.min_retrieval_confidence = min_retrieval_confidence
        super().__init__(
            rule_id="R4_CONFIDENCE_GATE",
            name="ConfidenceGate",
            trigger="Classifier confidence and retrieval confidence are both below their floors.",
            action="ESCALATE_LOW_CONFIDENCE",
            severity="block",
        )

    def evaluate(self, ctx: RuleContext) -> RuleEvaluation:
        """
        Overrides the base class because this rule's severity is conditional.

        With every supplied signal below its floor the gate blocks; with at least
        one signal above it the same findings are demoted to warnings. Encoding
        that as one evaluation keeps the verdict honest — the audit trail shows
        `low_retrieval_confidence` either way, but only the all-low case stops the
        answer.
        """
        if ctx.crop_confidence is None and ctx.retrieval_confidence is None:
            return RuleEvaluation(
                rule_id=self.rule_id,
                name=self.name,
                trigger=self.trigger,
                action=self.action,
                severity=self.severity,
                status="not_evaluated",
                note="no confidence signal supplied",
            )

        findings = self._signal_findings(ctx)
        below = {f.detail.get("signal") for f in findings}
        supplied = {
            name
            for name, value in (
                ("classifier", ctx.crop_confidence),
                ("retrieval", ctx.retrieval_confidence),
            )
            if value is not None
        }
        blocking = findings and below >= supplied

        if blocking:
            findings = [self._block_finding(ctx, sorted(below))] + findings

        return RuleEvaluation(
            rule_id=self.rule_id,
            name=self.name,
            trigger=self.trigger,
            action=self.action,
            severity="block" if blocking else "warn",
            status="triggered" if findings else "passed",
            findings=findings,
        )

    def check(self, ctx: RuleContext) -> tuple[list[RuleFinding], Optional[str]]:
        # Kept for interface completeness; `evaluate` above is the implementation.
        return self._signal_findings(ctx), None

    def _signal_findings(self, ctx: RuleContext) -> list[RuleFinding]:
        findings: list[RuleFinding] = []

        if ctx.crop_confidence is not None:
            if ctx.crop_confidence < self.min_classifier_confidence:
                findings.append(RuleFinding(
                    code="low_classifier_confidence",
                    message_en="The crop was not identified with confidence.",
                    message_hi="फसल की पहचान विश्वास के साथ नहीं हो सकी।",
                    detail={
                        "signal": "classifier",
                        "crop_confidence": round(ctx.crop_confidence, 3),
                        "floor": self.min_classifier_confidence,
                    },
                ))

        if ctx.retrieval_confidence is not None:
            if ctx.retrieval_confidence < self.min_retrieval_confidence:
                findings.append(RuleFinding(
                    code="low_retrieval_confidence",
                    message_en="No sufficiently related passage was found in the knowledge base.",
                    message_hi="ज्ञान-आधार में कोई पर्याप्त संबंधित अंश नहीं मिला।",
                    detail={
                        "signal": "retrieval",
                        "retrieval_confidence": round(ctx.retrieval_confidence, 3),
                        "top_similarity": (
                            round(ctx.top_similarity, 3) if ctx.top_similarity is not None else None
                        ),
                        "floor": self.min_retrieval_confidence,
                    },
                ))
        return findings

    def _block_finding(self, ctx: RuleContext, below: Sequence[str]) -> RuleFinding:
        return RuleFinding(
            code="no_signal_cleared_floor",
            message_en="The crop could not be identified confidently and the knowledge base "
                       "returned no sufficiently related passage. Please name the crop and the "
                       "pest, or ask your local extension officer.",
            message_hi="फसल की पहचान विश्वास के साथ नहीं हो सकी और ज्ञान-आधार से कोई पर्याप्त "
                       "संबंधित अंश नहीं मिला। कृपया फसल और कीट का नाम बताएँ, या अपने स्थानीय "
                       "कृषि विस्तार अधिकारी से पूछें।",
            detail={"below_floor": list(below)},
        )


# ---------------------------------------------------------------------------
# R5
# ---------------------------------------------------------------------------
class StaleSourceCheck(Rule):
    """
    An old source is a warning, never a refusal.

    Two distinct gaps are reported: a source that is older than the freshness
    window, and a source that publishes no date at all (its currency cannot be
    established). The second is the more common case in this pilot — five of the
    eight sources carry no date — so reporting only the first would understate
    the problem.
    """

    def __init__(self, freshness_years: int = 5) -> None:
        self.freshness_years = freshness_years
        super().__init__(
            rule_id="R5_STALE_SOURCE_CHECK",
            name="StaleSourceCheck",
            trigger=f"Matched source's publication date is older than {freshness_years} years, "
                    f"or no publication date is published.",
            action="WARN_VERIFY_CURRENCY",
            severity="warn",
        )

    def check(self, ctx: RuleContext) -> tuple[list[RuleFinding], Optional[str]]:
        if not ctx.records:
            return [], "no record selected, so there is no source to check"

        findings: list[RuleFinding] = []
        seen: set[str] = set()
        for record in ctx.records:
            source = ctx.source_for(record)
            if source is None or source.source_id in seen:
                continue
            seen.add(source.source_id)

            if not source.publication_date:
                findings.append(RuleFinding(
                    code="publication_date_not_published",
                    message_en="The source for this record publishes no date, so its currency "
                               "cannot be established. Confirm it is still current before relying "
                               "on it.",
                    message_hi="इस रिकॉर्ड का स्रोत कोई प्रकाशन तिथि नहीं देता, इसलिए इसकी "
                               "वर्तमानता स्थापित नहीं की जा सकती। इस पर भरोसा करने से पहले पुष्टि "
                               "करें कि यह अभी भी मान्य है।",
                    detail={"source_id": source.source_id, "record_id": record.approved_use_id},
                ))
                continue

            age = _age_years(source.publication_date, ctx.today)
            if age is not None and age > self.freshness_years:
                findings.append(RuleFinding(
                    code="source_older_than_freshness_window",
                    message_en=f"The source for this record was published about {age} years ago. "
                               f"Confirm it is still current before relying on it.",
                    message_hi=f"इस रिकॉर्ड का स्रोत लगभग {age} वर्ष पहले प्रकाशित हुआ था। इस पर "
                               f"भरोसा करने से पहले पुष्टि करें कि यह अभी भी मान्य है।",
                    detail={
                        "source_id": source.source_id,
                        "publication_date": source.publication_date,
                        "age_years": age,
                        "window_years": self.freshness_years,
                    },
                ))
        return findings, None


def _age_years(publication_date: str, today: date) -> Optional[int]:
    """
    Whole years since a partially specified date ('2023-05', '2014-03-06').

    Month-only dates are read as the first of that month, which can overstate the
    age by at most one month — and overstating age only ever adds a warning, so
    the direction of the error is the safe one.
    """
    parts = publication_date.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        published = date(year, month, day)
    except (ValueError, IndexError):
        return None
    return int((today - published).days // 365.25)


# Reporting order follows the blueprint's table (R1..R5). Blocking precedence is
# a separate concern and lives in engine.BLOCK_PRECEDENCE; running the rules in
# R1..R5 order means the response reads like the specification it implements.
DEFAULT_RULES: tuple[Rule, ...] = (
    RequireApprovedPair(),
    RequireSafetyFields(),
    ContradictionCheck(),
    ConfidenceGate(),
    StaleSourceCheck(),
)
