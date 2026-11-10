"""
Phase 7 tests — the rule-based safety engine.

The blueprint (§12) requires "explicit unit tests per rule (e.g., 'missing PHI
field -> must escalate', 'two contradicting dosage sources -> must escalate,
never average or guess')", with pass/fail counted. That is the structure here:
every rule has its own cases with hand-built records, so a failure names the rule
and the trigger rather than an end-to-end outcome.

The negative cases carry the weight. A rule engine that passes everything is
indistinguishable from an absent one, so each rule is asserted both ways: it
fires on the condition it declares, and it stays silent when the condition is
met by a complete record.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.knowledge_base.models import ApprovedUse, Intervention, SafetyField, SafetyRestrictions, Source
from app.rag.pipeline import KnowledgeBundle, answer_query, reset_bundle_cache
from app.rag.schemas import RAG_OUTCOMES, RagRequest
from app.rules import (
    BLOCK_PRECEDENCE,
    ESCALATION_MESSAGES,
    RULE_IDS,
    ContradictionCheck,
    RuleContext,
    RuleEngine,
    RuleEngineInconsistency,
    StaleSourceCheck,
    assert_consistency,
    escalation_message,
    get_rule_engine,
    is_fully_published,
    missing_safety_fields,
)
from app.vector.chunking import build_chunks
from app.vector.store import InMemoryVectorStore

TODAY = date(2026, 11, 3)


# ---------------------------------------------------------------------------
# fixtures: hand-built records, so a rule can be exercised without a database
# ---------------------------------------------------------------------------
def make_source(
    source_id: str = "SRC-TEST-01",
    publication_date: str | None = "2024-01",
) -> Source:
    return Source(
        source_id=source_id,
        title=f"Test source {source_id}",
        authority="Test authority",
        url=f"https://example.org/{source_id}",
        publication_date=publication_date,
        publication_date_note=None if publication_date else "page publishes no date",
        retrieved_date="2026-11-02",
        geography="India",
        reliability_tier="state_agricultural_university",
    )


def published(value: str) -> SafetyField:
    return SafetyField(status="PUBLISHED", value=value)


def unpublished(note: str = "not stated in source") -> SafetyField:
    return SafetyField(status="NOT_PUBLISHED_IN_SOURCE", note=note)


def make_record(
    record_id: str = "AU-TEST-01",
    *,
    crop: str = "cotton",
    pest: str = "Test borer",
    source_id: str = "SRC-TEST-01",
    phi: SafetyField | None = None,
    rei: SafetyField | None = None,
    ppe: SafetyField | None = None,
    dosage: str | None = "1 ml per litre",
    chemical: bool = True,
    extra_interventions: list[Intervention] | None = None,
) -> ApprovedUse:
    interventions: list[Intervention] = []
    if chemical:
        interventions.append(
            Intervention(
                control_type="chemical",
                description="Spray the test product",
                active_ingredient_and_formulation="Test active 10% EC",
                dosage=dosage,
            )
        )
    else:
        interventions.append(
            Intervention(control_type="cultural", description="Remove and destroy affected shoots")
        )
    interventions.extend(extra_interventions or [])

    return ApprovedUse(
        approved_use_id=record_id,
        crop_id=crop,
        target_pest_common_name=pest,
        target_pest_scientific_name="Testus borerus",
        interventions=interventions,
        safety_restrictions=SafetyRestrictions(
            phi=phi or published("7 days"),
            rei=rei or published("24 hours"),
            ppe=ppe or published("Gloves and a mask"),
        ),
        source_id=source_id,
        verification_status="VERIFIED_SOURCE_RECOMMENDATION",
        verification_note="Test fixture; transcribed from a synthetic source. Not a real record.",
    )


def _default_sources(records) -> dict[str, Source]:
    ids = {r.source_id for r in records} or {"SRC-TEST-01"}
    return {source_id: make_source(source_id) for source_id in ids}


def verified_evidence(*record_ids: str) -> dict:
    """
    A *valid* evidence object for tests.

    Deliberately not a boolean: `is_verified` type-checks for `RegulatoryEvidence`,
    so `{id: True}` is exactly the forgery the security audit must reject.
    """
    from app.rules.verification import RegulatoryEvidence

    return {
        rid: RegulatoryEvidence(
            record_id=rid,
            registry="CIBRC",
            registry_reference=f"CIB&RC/2026/{rid}",
            verified_on=date(2026, 10, 1),
            evidence_url="https://ppqs.gov.in/divisions/cib-rc/registered-products",
            evidence_sha256="a" * 64,
            verified_by="Test reviewer",
        )
        for rid in record_ids
    }


def context(records=(), **kwargs) -> RuleContext:
    records = tuple(records)
    all_records = kwargs.pop("all_records", {r.approved_use_id: r for r in records})
    sources = kwargs.pop("sources", _default_sources(records))
    return RuleContext(
        records=records,
        all_records=all_records,
        sources=sources,
        today=TODAY,
        **kwargs,
    )


@pytest.fixture(scope="module")
def engine() -> RuleEngine:
    return RuleEngine()


@pytest.fixture(scope="module")
def json_repo() -> JSONFileKnowledgeBaseRepository:
    return JSONFileKnowledgeBaseRepository()


@pytest.fixture(scope="module")
def offline_store(json_repo) -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    store.upsert_chunks(
        build_chunks(
            json_repo.list_approved_uses(), json_repo.list_crops(), json_repo.list_sources()
        )
    )
    return store


@pytest.fixture(scope="module")
def bundle(json_repo) -> KnowledgeBundle:
    return KnowledgeBundle(
        repository=json_repo,
        records={r.approved_use_id: r for r in json_repo.list_approved_uses()},
        crops={c.crop_id: c for c in json_repo.list_crops()},
        sources={s.source_id: s for s in json_repo.list_sources()},
        provenance={},
    )


@pytest.fixture(scope="module")
def ask(bundle, offline_store):
    def _ask(query: str, **kwargs):
        return answer_query(RagRequest(query=query, **kwargs), store=offline_store, bundle=bundle)

    return _ask


def evaluation(verdict, rule_id: str):
    for item in verdict.evaluations:
        if item.rule_id == rule_id:
            return item
    raise AssertionError(f"{rule_id} missing from verdict")


def _has_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return any(_has_number(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_number(v) for v in value)
    return False


# ---------------------------------------------------------------------------
# R1 — RequireApprovedPair
# ---------------------------------------------------------------------------
class TestRequireApprovedPair:
    def test_no_record_blocks_with_missing_info(self, engine):
        verdict = engine.evaluate(context(records=(), crop_label="cotton"))
        rule = evaluation(verdict, "R1_REQUIRE_APPROVED_PAIR")
        assert rule.status == "triggered"
        assert rule.severity == "block"
        assert rule.findings[0].code == "no_record_for_crop_target"
        assert verdict.blocked is True
        assert verdict.blocking_action == "ESCALATE_MISSING_INFO"

    def test_crop_mismatch_blocks(self, engine):
        record = make_record(crop="cotton")
        verdict = engine.evaluate(context(records=[record], crop_label="rice"))
        rule = evaluation(verdict, "R1_REQUIRE_APPROVED_PAIR")
        assert rule.findings[0].code == "record_crop_mismatch"
        assert rule.findings[0].detail["record_crop"] == "cotton"
        assert rule.findings[0].detail["classified_crop"] == "rice"

    def test_record_missing_from_knowledge_base_blocks(self, engine):
        record = make_record(record_id="AU-GHOST-01")
        ctx = context(records=[record], crop_label="cotton", all_records={})
        verdict = engine.evaluate(ctx)
        assert evaluation(verdict, "R1_REQUIRE_APPROVED_PAIR").findings[0].code == (
            "record_missing_from_knowledge_base"
        )

    def test_matching_pair_passes(self, engine):
        record = make_record(crop="cotton", pest="Pink bollworm")
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        assert evaluation(verdict, "R1_REQUIRE_APPROVED_PAIR").status == "passed"

    def test_uncovered_pest_is_blocked_on_the_standalone_surface(self, engine):
        record = make_record(crop="cotton", pest="Pink bollworm")
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", target_pest="whitefly")
        )
        codes = [f.code for f in evaluation(verdict, "R1_REQUIRE_APPROVED_PAIR").findings]
        assert "target_pest_not_covered" in codes

    def test_covered_pest_passes(self, engine):
        record = make_record(crop="cotton", pest="Pink bollworm")
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", target_pest="pink bollworm")
        )
        assert evaluation(verdict, "R1_REQUIRE_APPROVED_PAIR").status == "passed"


# ---------------------------------------------------------------------------
# R2 — RequireSafetyFields
# ---------------------------------------------------------------------------
class TestRequireSafetyFields:
    def test_complete_profile_with_a_recorded_registration_check_is_actionable(self, engine):
        """
        Both halves are required: a complete PHI/REI/PPE profile *and* a recorded
        CIB&RC verification. Safety completeness alone is not enough (see the next
        test), and nothing in this project has ever queried the CIB&RC registry.
        """
        record = make_record()
        verdict = engine.evaluate(
            context(
                records=[record],
                crop_label="cotton",
                regulatory_verification=verified_evidence(record.approved_use_id),
            )
        )
        assert evaluation(verdict, "R2_REQUIRE_SAFETY_FIELDS").status == "passed"
        assert verdict.blocked is False
        assert verdict.actionability == "ACTIONABLE_WITH_EVIDENCE"
        assert verdict.decision == "ACTIONABLE_RECOMMENDATION"
        assert verdict.missing_information == []

    def test_complete_profile_without_a_registration_check_is_not_actionable(self, engine):
        """
        The source-transcribed recommendation is not a regulatory approval.

        `verification_status` is `VERIFIED_SOURCE_RECOMMENDATION`, which the model's
        own docstring defines as "not cross-checked against the live CIB&RC
        registry". Presenting that as an actionable dose would collapse the exact
        distinction DEC-010 exists to preserve.
        """
        record = make_record()
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        rule = evaluation(verdict, "R2_REQUIRE_SAFETY_FIELDS")
        codes = [f.code for f in rule.findings]
        assert codes == ["regulatory_approval_not_verified"]
        assert rule.status == "triggered"
        assert verdict.blocked is False
        assert verdict.actionability == "EDUCATIONAL_ONLY"
        assert verdict.decision == "REGULATORY_VERIFICATION_REQUIRED"
        assert verdict.missing_information == ["regulatory_approval"]

    def test_missing_phi_restricts_actionability_but_not_the_answer(self, engine):
        record = make_record(phi=unpublished())
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        rule = evaluation(verdict, "R2_REQUIRE_SAFETY_FIELDS")
        assert rule.status == "triggered"
        assert rule.severity == "restrict_actionability"
        assert rule.findings[0].detail["missing_fields"] == ["phi"]
        assert verdict.blocked is False, "an educational answer is still allowed"
        assert verdict.actionability == "EDUCATIONAL_ONLY"

    def test_one_incomplete_chemical_option_restricts_the_whole_record(self, engine):
        """
        PHI/REI attach to a product, not to a record. A record offering two
        interchangeable products is only actionable if both are complete.
        """
        partial = Intervention(
            control_type="chemical",
            description="Second option",
            active_ingredient_and_formulation="Other active 5% SC",
            dosage="2 ml per litre",
            safety_restrictions=SafetyRestrictions(
                phi=unpublished(), rei=published("24 hours"), ppe=published("Gloves")
            ),
        )
        record = make_record(extra_interventions=[partial])
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        assert evaluation(verdict, "R2_REQUIRE_SAFETY_FIELDS").status == "triggered"
        assert verdict.actionability == "EDUCATIONAL_ONLY"

    def test_missing_dosage_is_reported_as_missing_information(self, engine):
        record = make_record(dosage=None)
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        rule = evaluation(verdict, "R2_REQUIRE_SAFETY_FIELDS")
        assert "dosage" in rule.findings[0].detail["missing_fields"]

    def test_record_without_a_chemical_measure_is_never_actionable(self, engine):
        record = make_record(chemical=False)
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        assert evaluation(verdict, "R2_REQUIRE_SAFETY_FIELDS").findings[0].code == (
            "no_chemical_intervention"
        )
        assert verdict.actionability == "EDUCATIONAL_ONLY"

    def test_every_shipped_record_is_educational_only(self, engine, json_repo):
        for record in json_repo.list_approved_uses():
            verdict = engine.evaluate(context(records=[record], crop_label=record.crop_id))
            assert verdict.blocked is False, record.approved_use_id
            assert verdict.actionability == "EDUCATIONAL_ONLY", record.approved_use_id
            assert missing_safety_fields(record), record.approved_use_id


# ---------------------------------------------------------------------------
# R3 — ContradictionCheck
# ---------------------------------------------------------------------------
class TestContradictionCheck:
    def test_two_sources_disagreeing_on_phi_block(self, engine):
        first = make_record(record_id="AU-A", source_id="SRC-A", phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-B", phi=published("21 days"))
        verdict = engine.evaluate(context(records=[first, second], crop_label="cotton"))

        rule = evaluation(verdict, "R3_CONTRADICTION_CHECK")
        assert rule.status == "triggered"
        assert rule.findings[0].code == "phi_conflicts_across_sources"
        assert verdict.blocked is True
        assert verdict.blocking_action == "ESCALATE_CONTRADICTION"

    def test_agreement_is_not_a_contradiction(self, engine):
        first = make_record(record_id="AU-A", source_id="SRC-A", phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-B", phi=published("7 days"))
        verdict = engine.evaluate(context(records=[first, second], crop_label="cotton"))
        assert evaluation(verdict, "R3_CONTRADICTION_CHECK").status == "passed"

    def test_tolerance_absorbs_a_one_day_difference(self):
        strict = ContradictionCheck(tolerance_days=0.0)
        lenient = ContradictionCheck(tolerance_days=1.0)
        first = make_record(record_id="AU-A", source_id="SRC-A", phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-B", phi=published("8 days"))
        ctx = context(records=[first, second], crop_label="cotton")
        assert strict.evaluate(ctx).status == "triggered"
        assert lenient.evaluate(ctx).status == "passed"

    def test_same_source_is_not_a_cross_source_contradiction(self, engine):
        """The blueprint scopes this rule to chunks from *different* sources."""
        first = make_record(record_id="AU-A", source_id="SRC-A", phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-A", phi=published("21 days"))
        verdict = engine.evaluate(context(records=[first, second], crop_label="cotton"))
        assert evaluation(verdict, "R3_CONTRADICTION_CHECK").status == "passed"

    def test_different_pests_are_not_compared(self, engine):
        first = make_record(record_id="AU-A", source_id="SRC-A", pest="Pink bollworm",
                            phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-B", pest="Spotted bollworm",
                             phi=published("21 days"))
        verdict = engine.evaluate(context(records=[first, second], crop_label="cotton"))
        assert evaluation(verdict, "R3_CONTRADICTION_CHECK").status == "passed"

    def test_a_record_contradicting_itself_blocks(self, engine):
        contradictory = Intervention(
            control_type="chemical",
            description="Second option with a different label",
            active_ingredient_and_formulation="Other active 5% SC",
            dosage="2 ml per litre",
            safety_restrictions=SafetyRestrictions(
                phi=published("21 days"), rei=published("24 hours"), ppe=published("Gloves")
            ),
        )
        record = make_record(phi=published("7 days"), extra_interventions=[contradictory])
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        codes = [f.code for f in evaluation(verdict, "R3_CONTRADICTION_CHECK").findings]
        assert "phi_conflicts_within_record" in codes

    def test_the_withheld_values_never_appear_in_the_finding(self, engine):
        """
        A refusal that prints "7 vs 21 days" hands over the number it withheld.
        """
        first = make_record(record_id="AU-A", source_id="SRC-A", phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-B", phi=published("21 days"))
        verdict = engine.evaluate(context(records=[first, second], crop_label="cotton"))
        for finding in verdict.findings:
            assert not _has_number(finding.detail), finding.detail
            assert not any(ch.isdigit() for ch in finding.message_en)
            assert not any(ch.isdigit() for ch in finding.message_hi)


# ---------------------------------------------------------------------------
# R4 — ConfidenceGate
# ---------------------------------------------------------------------------
class TestConfidenceGate:
    def test_both_signals_low_blocks(self, engine):
        record = make_record()
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", crop_confidence=0.2,
                    retrieval_confidence=0.0)
        )
        rule = evaluation(verdict, "R4_CONFIDENCE_GATE")
        assert rule.status == "triggered"
        assert rule.severity == "block"
        assert rule.findings[0].code == "no_signal_cleared_floor"
        assert verdict.blocking_action == "ESCALATE_LOW_CONFIDENCE"

    def test_low_retrieval_alone_only_warns(self, engine):
        """
        Measured Phase 6 behaviour: the in-scope Hindi query scores 0.111 while an
        out-of-scope English query scores 0.311, so a similarity floor on its own
        would refuse the right question. A confident crop label must be enough.
        """
        record = make_record()
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", crop_confidence=0.85,
                    retrieval_confidence=0.0)
        )
        rule = evaluation(verdict, "R4_CONFIDENCE_GATE")
        assert rule.severity == "warn"
        assert rule.findings[0].code == "low_retrieval_confidence"
        assert verdict.blocked is False

    def test_low_classifier_alone_only_warns(self, engine):
        record = make_record()
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", crop_confidence=0.2,
                    retrieval_confidence=0.9)
        )
        rule = evaluation(verdict, "R4_CONFIDENCE_GATE")
        assert rule.severity == "warn"
        assert verdict.blocked is False

    def test_healthy_signals_pass(self, engine):
        record = make_record()
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", crop_confidence=0.9,
                    retrieval_confidence=0.8)
        )
        assert evaluation(verdict, "R4_CONFIDENCE_GATE").status == "passed"

    def test_absent_signals_are_not_evaluated_not_passed(self, engine):
        record = make_record()
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        rule = evaluation(verdict, "R4_CONFIDENCE_GATE")
        assert rule.status == "not_evaluated"
        assert rule.note

    def test_a_supplied_signal_below_floor_decides_alone(self, engine):
        record = make_record()
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", crop_confidence=0.1)
        )
        assert evaluation(verdict, "R4_CONFIDENCE_GATE").severity == "block"


# ---------------------------------------------------------------------------
# R5 — StaleSourceCheck
# ---------------------------------------------------------------------------
class TestStaleSourceCheck:
    def test_old_source_warns_without_blocking(self):
        """
        A warning cannot block even when it is the only rule that fires: the full
        engine is used here, so the assertion covers the verdict, not just the rule.
        """
        record = make_record(source_id="SRC-OLD")
        sources = {"SRC-OLD": make_source("SRC-OLD", publication_date="2014-03-06")}
        verdict = RuleEngine().evaluate(
            context(
                records=[record],
                crop_label="cotton",
                sources=sources,
                # Registration recorded, so actionability is decided by the stale
                # source alone — which is what this test is about.
                regulatory_verification=verified_evidence(record.approved_use_id),
            )
        )
        rule = evaluation(verdict, "R5_STALE_SOURCE_CHECK")
        assert rule.status == "triggered"
        assert rule.severity == "warn"
        assert rule.findings[0].code == "source_older_than_freshness_window"
        assert rule.findings[0].detail["age_years"] >= 12
        assert verdict.blocked is False
        assert verdict.actionability == "ACTIONABLE_WITH_EVIDENCE"
        assert StaleSourceCheck(freshness_years=5).evaluate(
            context(records=[record], crop_label="cotton", sources=sources)
        ).triggered

    def test_recent_source_passes(self, engine):
        record = make_record()
        verdict = engine.evaluate(context(records=[record], crop_label="cotton"))
        assert evaluation(verdict, "R5_STALE_SOURCE_CHECK").status == "passed"

    def test_undated_source_warns_about_unverifiable_currency(self, engine):
        record = make_record(source_id="SRC-UNDATED")
        sources = {"SRC-UNDATED": make_source("SRC-UNDATED", publication_date=None)}
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", sources=sources)
        )
        rule = evaluation(verdict, "R5_STALE_SOURCE_CHECK")
        assert rule.findings[0].code == "publication_date_not_published"
        assert verdict.blocked is False

    def test_missing_source_is_not_invented(self, engine):
        record = make_record(source_id="SRC-ABSENT")
        verdict = engine.evaluate(
            context(records=[record], crop_label="cotton", sources={})
        )
        assert evaluation(verdict, "R5_STALE_SOURCE_CHECK").status == "passed"


# ---------------------------------------------------------------------------
# escalation templates
# ---------------------------------------------------------------------------
class TestEscalation:
    def test_every_blocking_action_has_both_languages(self):
        for action in ("ESCALATE_MISSING_INFO", "ESCALATE_CONTRADICTION",
                       "ESCALATE_LOW_CONFIDENCE"):
            for language in ("en", "hi"):
                text = escalation_message(action, language)
                assert text, (action, language)
                assert not any(ch.isdigit() for ch in text), (action, language)

    def test_no_action_means_no_message(self):
        assert escalation_message(None, "en") == ""

    def test_hindi_and_english_differ(self):
        assert ESCALATION_MESSAGES["ESCALATE_CONTRADICTION"]["en"] != (
            ESCALATION_MESSAGES["ESCALATE_CONTRADICTION"]["hi"]
        )


# ---------------------------------------------------------------------------
# engine-level behaviour
# ---------------------------------------------------------------------------
class TestEngine:
    def test_registry_matches_the_declared_rule_set(self):
        engine = get_rule_engine()
        assert [r["rule_id"] for r in engine.registry()] == list(RULE_IDS)
        assert len(BLOCK_PRECEDENCE) == len(RULE_IDS)

    def test_duplicate_rule_is_rejected(self):
        engine = RuleEngine([ContradictionCheck(), ContradictionCheck()])
        with pytest.raises(RuleEngineInconsistency):
            engine.evaluate(context(records=[make_record()], crop_label="cotton"))

    def test_precedence_picks_missing_pair_over_a_contradiction(self, engine):
        first = make_record(record_id="AU-A", source_id="SRC-A", phi=published("7 days"))
        second = make_record(record_id="AU-B", source_id="SRC-B", phi=published("21 days"))
        verdict = engine.evaluate(context(records=[first, second], crop_label="rice"))
        assert verdict.blocking_action == "ESCALATE_MISSING_INFO"
        assert verdict.blocked is True

    def test_warnings_are_reported_but_do_not_block(self, engine):
        verdict = engine.evaluate(context(records=[make_record()], crop_label="cotton"))
        assert verdict.warnings == []
        assert set(e.rule_id for e in verdict.evaluations) == set(RULE_IDS)

    def test_trace_is_serialisable_and_names_what_ran(self, engine):
        verdict = engine.evaluate(
            context(records=[make_record()], crop_label="cotton", crop_confidence=0.9)
        )
        trace = verdict.trace
        assert trace["rules_run"] == list(RULE_IDS)
        assert trace["actionability"] in ("ACTIONABLE_WITH_EVIDENCE", "EDUCATIONAL_ONLY")
        assert trace["evaluated_on"] == TODAY.isoformat()
        assert trace["thresholds"]["min_classifier_confidence"] > 0
        import json

        json.dumps(trace)

    def test_shipped_knowledge_base_is_internally_consistent(self, json_repo):
        assert_consistency(json_repo.list_approved_uses())

    def test_disagreement_with_the_model_is_fatal(self, monkeypatch):
        """
        The rule engine and `advisory_status` are deliberately two
        implementations of one safety rule (as in Phase 5, Python + SQL). If they
        ever disagree, the request must fail rather than serve an ambiguous
        safety status.
        """
        record = make_record(phi=unpublished())
        assert is_fully_published(record) is False
        monkeypatch.setattr("app.rules.engine.is_fully_published", lambda _record: True)
        with pytest.raises(RuleEngineInconsistency):
            assert_consistency([record])


# ---------------------------------------------------------------------------
# integration with the Phase 6 pipeline
# ---------------------------------------------------------------------------
class TestPipelineIntegration:
    def test_answered_responses_carry_the_rule_verdict(self, ask):
        response = ask("pink bollworm management in cotton")
        assert response.outcome == "answered"
        assert response.rule_trace["evaluated"] is True
        assert response.rule_trace["rules_run"] == list(RULE_IDS)
        assert response.rule_findings
        codes = {f["code"] for f in response.rule_findings}
        assert "safety_fields_not_published" in codes

    def test_rule_findings_are_localised(self, ask):
        response = ask("pink bollworm management in cotton", language="hi")
        assert response.answer_language == "hi"
        messages = [f["message"] for f in response.rule_findings]
        assert messages
        assert any("\u0900" <= ch <= "\u097f" for ch in " ".join(messages))

    def test_actionability_comes_from_the_verdict(self, ask):
        response = ask("fall armyworm in maize")
        assert response.advisory_status == "EDUCATIONAL_ONLY"
        assert any(
            f["code"] == "safety_fields_not_published" for f in response.rule_findings
        )

    def test_refusals_before_record_selection_record_why_rules_did_not_run(self, ask):
        response = ask("whitefly on cotton")
        assert response.outcome == "insufficient_evidence"
        assert response.rule_trace["evaluated"] is False
        assert response.rule_trace["reason"] == "decision_gate_refused_before_record_selection"
        assert response.rule_findings == []

    def test_hindi_query_is_warned_not_blocked(self, ask):
        response = ask("कपास में गुलाबी सुंडी")
        assert response.outcome == "answered"
        codes = {f["code"] for f in response.rule_findings}
        assert "low_retrieval_confidence" in codes
        assert response.rule_trace["blocking_rule"] is None

    def test_every_outcome_stays_inside_the_declared_enum(self, ask):
        for query in (
            "pink bollworm in cotton",
            "whitefly on cotton",
            "how long before harvest after spraying cotton",
            "is chlorpyriphos approved for rice",
            "how do I fix my tractor engine",
            "hello",
            "कपास में गुलाबी सुंडी",
        ):
            response = ask(query)
            assert response.outcome in RAG_OUTCOMES, (query, response.outcome)

    def test_rule_evaluation_is_deterministic(self, ask):
        first = ask("termite in wheat")
        second = ask("termite in wheat")
        assert first.rule_trace == second.rule_trace
        assert first.rule_findings == second.rule_findings


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------
@pytest.fixture()
def client(bundle, offline_store, monkeypatch) -> TestClient:
    from app.main import app
    import app.rag.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "get_repository_bundle", lambda: bundle)
    monkeypatch.setattr(pipeline_module, "get_vector_store", lambda: offline_store)
    reset_bundle_cache()
    yield TestClient(app)
    reset_bundle_cache()


class TestApi:
    def test_status_reports_the_registry(self, client):
        response = client.get("/rules/status")
        assert response.status_code == 200
        body = response.json()
        assert [r["rule_id"] for r in body["rules"]] == list(RULE_IDS)
        assert body["knowledge_base"]["records"] == 9
        assert body["knowledge_base"]["actionable_with_evidence"] == 0
        assert body["knowledge_base"]["educational_only"] == 9
        assert body["generation_involvement"] == "none"

    def test_evaluate_a_crop_without_running_retrieval(self, client):
        response = client.post("/rules/evaluate", json={"crop": "cotton"})
        assert response.status_code == 200
        body = response.json()
        assert body["blocked"] is False
        assert body["actionability"] == "EDUCATIONAL_ONLY"
        assert len(body["records_evaluated"]) == 3
        triggered = [e["rule_id"] for e in body["evaluations"] if e["status"] == "triggered"]
        assert "R2_REQUIRE_SAFETY_FIELDS" in triggered
        # No confidence was supplied, so the gate must say so rather than pass.
        gate = next(e for e in body["evaluations"] if e["rule_id"] == "R4_CONFIDENCE_GATE")
        assert gate["status"] == "not_evaluated"
        assert gate["note"]

    def test_evaluate_an_uncovered_pest_escalates_missing_info(self, client):
        response = client.post(
            "/rules/evaluate", json={"crop": "cotton", "target_pest": "whitefly"}
        )
        body = response.json()
        assert body["blocked"] is True
        assert body["blocking_action"] == "ESCALATE_MISSING_INFO"
        assert body["message"]
        assert body["records_evaluated"] == []

    def test_low_confidence_escalates_clarification(self, client):
        response = client.post(
            "/rules/evaluate",
            json={"crop": "cotton", "classifier_confidence": 0.1, "retrieval_confidence": 0.0},
        )
        body = response.json()
        assert body["blocking_action"] == "ESCALATE_LOW_CONFIDENCE"
        assert body["evaluations"]
        assert "name the crop" in body["message"]

    def test_hindi_messages_are_returned_on_request(self, client):
        response = client.post(
            "/rules/evaluate", json={"crop": "cotton", "language": "hi"}
        )
        body = response.json()
        messages = [
            finding["message"]
            for evaluation_ in body["evaluations"]
            for finding in evaluation_["findings"]
        ]
        assert messages
        assert any("\u0900" <= ch <= "\u097f" for ch in " ".join(messages))

    def test_unknown_record_id_is_a_404(self, client):
        response = client.post("/rules/evaluate", json={"crop": "cotton", "record_ids": ["AU-NOPE"]})
        assert response.status_code == 404

    def test_unknown_field_is_rejected(self, client):
        response = client.post("/rules/evaluate", json={"crop": "cotton", "temperature": 4})
        assert response.status_code == 422

    def test_rag_status_reports_the_rule_engine(self, client):
        body = client.get("/rag/status").json()
        assert body["rule_engine"]["rules"]
        assert body["rule_engine"]["thresholds"]["source_freshness_years"] >= 1

    def test_existing_routes_still_work(self, client):
        for path in ("/health", "/knowledge-base/crops", "/rag/status", "/rules/status"):
            assert client.get(path).status_code == 200, path
