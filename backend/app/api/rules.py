"""
Phase 7 API — the rule engine, callable on its own.

POST /rules/evaluate   run all five rules against the knowledge base for a crop
                       (optionally a pest or an explicit record set)
GET  /rules/status     the rule registry, thresholds, and how many records could
                       currently be actionable

Both endpoints are read-only: they evaluate and report, they never write to the
knowledge base and never change a record's status. The same engine runs inside
`POST /rag/answer`; this surface exists so the gate can be inspected and graded
independently of answer composition.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from app.knowledge_base.factory import KnowledgeBaseRepositoryUnavailable, get_knowledge_base_repository
from app.rules.context import RuleContext, is_fully_published, normalize_pest
from app.rules.engine import RuleEngineInconsistency, get_rule_engine, rule_engine_status
from app.rules.escalation import escalation_message
from app.schemas.rules import (
    RuleEvaluateRequest,
    RuleEvaluateResponse,
    RuleEvaluationOut,
    RuleFindingOut,
    RuleStatusResponse,
)

router = APIRouter(prefix="/rules", tags=["rules"])


def _knowledge_base() -> tuple[dict, dict]:
    repository = get_knowledge_base_repository()
    records = {r.approved_use_id: r for r in repository.list_approved_uses()}
    sources = {s.source_id: s for s in repository.list_sources()}
    return records, sources


@router.post("/evaluate", response_model=RuleEvaluateResponse)
def evaluate_rules(payload: RuleEvaluateRequest) -> RuleEvaluateResponse:
    try:
        records_by_id, sources = _knowledge_base()
    except KnowledgeBaseRepositoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    crop = payload.crop.strip().lower()
    if payload.record_ids:
        selected = [records_by_id[rid] for rid in payload.record_ids if rid in records_by_id]
        unknown = [rid for rid in payload.record_ids if rid not in records_by_id]
        if unknown:
            raise HTTPException(
                status_code=404,
                detail=f"unknown approved_use id(s): {', '.join(sorted(unknown))}",
            )
    else:
        selected = [r for r in records_by_id.values() if r.crop_id == crop]

    if payload.target_pest:
        pest_tokens = set(normalize_pest(payload.target_pest).split())
        matched = [
            r for r in selected
            if pest_tokens <= set(normalize_pest(r.target_pest_common_name).split())
        ]
        # A pest filter that matches nothing must not silently fall back to the
        # whole crop: that would evaluate a different question and report the
        # result under the requested pest.
        selected = matched

    try:
        verdict = get_rule_engine().evaluate(
            RuleContext(
                crop_label=crop,
                records=tuple(selected),
                all_records=records_by_id,
                sources=sources,
                target_pest=payload.target_pest,
                crop_confidence=payload.classifier_confidence,
                retrieval_confidence=payload.retrieval_confidence,
            )
        )
    except RuleEngineInconsistency as exc:
        # Fail closed and say why. Serving a verdict whose actionability two
        # implementations disagree about would be worse than serving none.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RuleEvaluateResponse(
        crop=crop,
        target_pest=payload.target_pest,
        records_evaluated=[r.approved_use_id for r in selected],
        blocked=verdict.blocked,
        blocking_action=verdict.blocking_action,
        actionability=verdict.actionability,
        decision=verdict.decision,
        missing_information=verdict.missing_information,
        message=escalation_message(verdict.blocking_action, payload.language),
        evaluations=[
            RuleEvaluationOut(
                rule_id=evaluation.rule_id,
                name=evaluation.name,
                trigger=evaluation.trigger,
                action=evaluation.action,
                severity=evaluation.severity,
                status=evaluation.status,
                note=evaluation.note,
                findings=[
                    RuleFindingOut(
                        rule_id=evaluation.rule_id,
                        code=finding.code,
                        severity=evaluation.severity,
                        action=evaluation.action,
                        message=finding.message(payload.language),
                        detail=finding.detail,
                    )
                    for finding in evaluation.findings
                ],
            )
            for evaluation in verdict.evaluations
        ],
        trace=verdict.trace,
    )


@router.get("/status", response_model=RuleStatusResponse)
def rules_status() -> RuleStatusResponse:
    try:
        records_by_id, sources = _knowledge_base()
    except KnowledgeBaseRepositoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Ask the engine itself, record by record, instead of restating its rule here.
    # A separate summary definition is what previously let this endpoint's "reason"
    # describe a weaker gate than the one that actually decides.
    engine = get_rule_engine()
    actionable: list[str] = []
    for record in records_by_id.values():
        verdict = engine.evaluate(
            RuleContext(
                crop_label=record.crop_id,
                records=(record,),
                all_records=records_by_id,
                sources=sources,
                today=date.today(),
            )
        )
        if verdict.decision == "ACTIONABLE_RECOMMENDATION":
            actionable.append(record.approved_use_id)

    safety_complete = [r.approved_use_id for r in records_by_id.values() if is_fully_published(r)]
    status = rule_engine_status()
    return RuleStatusResponse(
        **status,
        knowledge_base={
            "records": len(records_by_id),
            "actionable_with_evidence": len(actionable),
            "educational_only": len(records_by_id) - len(actionable),
            "actionable_record_ids": sorted(actionable),
            "safety_profile_complete": len(safety_complete),
            "regulatory_verifications_recorded": 0,
            "reason": "A record is actionable only when every chemical intervention has a "
            "PUBLISHED PHI, REI and PPE value AND a CIB&RC registration check is recorded for "
            "it. No source fetched so far publishes the first, and this project has never "
            "queried the CIB&RC registry, so no record is actionable.",
        },
    )
