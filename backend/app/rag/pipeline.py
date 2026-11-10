"""
Phase 6/7 — the RAG pipeline.

    query
      -> Phase 4 classifier            (crop / task / safety topic, language)
      -> embedding + vector search     (Phase 5 store: pgvector or exact scan)
      -> crop + pest conditioned rank  (deterministic, explainable)
      -> decision gate                 (classifier + crop agreement, not similarity)
      -> Phase 7 rule engine           (veto / restrict actionability / warn)
      -> extractive grounded assembly  (knowledge-base fields only)
      -> citations + safety disclosures + confidence

The decision is made *before* any text is composed, so a confident-sounding
paragraph can never be produced for a question the assistant should decline.
Nothing here calls a generative model; `generation_mode` says so explicitly.

Phase 7 placement: the rule engine runs on the *selected records*, after the
decision gate and before composition. It is the last thing between the knowledge
base and the user, which is where blueprint §11 puts it — with veto power over
whether anything reaches the answer at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.classification.service import classify_query
from app.knowledge_base.models import ApprovedUse, Crop, Source
from app.knowledge_base.repository import KnowledgeBaseRepository
from app.rag import evidence as ev
from app.rag.generation import build_answer, build_crop_answer, outcome_message
from app.rag.schemas import Citation, EvidenceItem, RagRequest, RagResponse, SafetyDisclosure
from app.rules.context import RuleContext
from app.rules.engine import get_rule_engine, rule_engine_status
from app.rules.escalation import escalation_message
from app.vector.embedding import get_embedding_provider
from app.vector.store import VectorStore, get_vector_store

CLASSIFIER_VERSION_FALLBACK = "unknown"
MAX_CROP_RECORDS = 4

# Which refusal the user sees for each blocking rule action. Kept as one table so
# a rule and its outcome cannot drift apart: every ESCALATE_* value must be here,
# and a test asserts the table covers the enum exactly.
OUTCOME_BY_ACTION = {
    "ESCALATE_MISSING_INFO": "insufficient_evidence",
    "ESCALATE_CONTRADICTION": "safety_contradiction",
    "ESCALATE_LOW_CONFIDENCE": "needs_clarification",
}

# A query the Phase 6 decision gate refused is never handed to the rule engine —
# there are no selected records for it to evaluate. Leaving `decision` null there
# would mean the Phase 7 decision classes silently stop at the gate, so each
# gate outcome is mapped to the class it already represents. This adds no new
# refusal behaviour: the outcome, message and (absent) answer are unchanged.
DECISION_BY_GATE_OUTCOME = {
    "needs_clarification": "CLARIFICATION_REQUIRED",
    "out_of_scope": "ESCALATION_REQUIRED",
    "unsupported_crop": "ESCALATION_REQUIRED",
    "insufficient_evidence": "ESCALATION_REQUIRED",
    "safety_value_not_published": "SAFETY_REFUSAL",
    "no_regulatory_verification": "REGULATORY_VERIFICATION_REQUIRED",
}

# Which field is missing, for the two gate outcomes that name one.
MISSING_FOR_GATE_OUTCOME = {
    "no_regulatory_verification": ["regulatory_approval"],
}


@dataclass(frozen=True)
class KnowledgeBundle:
    repository: KnowledgeBaseRepository
    records: dict[str, ApprovedUse]
    crops: dict[str, Crop]
    sources: dict[str, Source]
    provenance: dict[str, str]


_bundle: Optional[KnowledgeBundle] = None
_regulatory_evidence: Optional[dict] = None


def get_regulatory_evidence() -> dict:
    """
    Backend-loaded CIB&RC verification evidence, memoised.

    Deliberately not a parameter of `answer_query`: an evidence argument would be
    one refactor away from being populated from a request. The only source is the
    git-tracked manifest under `knowledge_base/seed_data/`, read once per process.

    A malformed manifest is swallowed here and reported as no evidence, because
    the failure direction must be "closed". `load_regulatory_evidence()` still
    raises for callers (and the security tests) that want the specific error.
    """
    global _regulatory_evidence
    if _regulatory_evidence is None:
        try:
            from app.rules.verification import load_regulatory_evidence

            _regulatory_evidence = load_regulatory_evidence()
        except Exception:  # noqa: BLE001 - fail closed, never open
            _regulatory_evidence = {}
    return _regulatory_evidence


def reset_regulatory_evidence() -> None:
    global _regulatory_evidence
    _regulatory_evidence = None


def get_repository_bundle() -> KnowledgeBundle:
    """
    Load the knowledge base once per process.

    Provenance is optional: a missing manifest must not prevent answering, it only
    means a citation cannot show a document digest.
    """
    global _bundle
    if _bundle is not None:
        return _bundle

    from app.knowledge_base.factory import get_knowledge_base_repository

    repository = get_knowledge_base_repository()
    records = {r.approved_use_id: r for r in repository.list_approved_uses()}
    crops = {c.crop_id: c for c in repository.list_crops()}
    sources = {s.source_id: s for s in repository.list_sources()}

    provenance: dict[str, str] = {}
    if hasattr(repository, "list_provenance"):
        try:
            provenance = ev.provenance_index(repository.list_provenance())
        except Exception:  # noqa: BLE001 - provenance is an enhancement, not a prerequisite
            provenance = {}
    if not provenance:
        # The JSON repository keeps no provenance table, but the Phase 3.1 audit
        # manifest holds the same per-record document digests. Without this
        # fallback every citation from a JSON-backed run would silently lose its
        # `provenance_sha256` — a quieter loss of traceability than a failure.
        try:
            from app.knowledge_base.provenance import load_provenance_manifest

            provenance = {
                item.approved_use_id: item.document_sha256[:16]
                for item in load_provenance_manifest()
                if item.document_sha256
            }
        except Exception:  # noqa: BLE001
            provenance = {}

    _bundle = KnowledgeBundle(repository, records, crops, sources, provenance)
    return _bundle


def reset_bundle_cache() -> None:
    global _bundle
    _bundle = None


def _resolve_language(requested: Optional[str], detected: str) -> str:
    if requested in ("en", "hi"):
        return requested
    return "hi" if detected in ("hi", "hi-latn") else "en"


def _response(
    *,
    request: RagRequest,
    language: str,
    outcome: str,
    classification: dict,
    confidence: float,
    components: dict,
    model_versions: dict,
    message: Optional[str] = None,
    answer: Optional[str] = None,
    sections: Optional[list[dict]] = None,
    citations: Optional[list[Citation]] = None,
    evidence: Optional[list[EvidenceItem]] = None,
    disclosures: Optional[list[dict]] = None,
    advisory_status: Optional[str] = None,
    scope: str = "record",
    rule_findings: Optional[list[dict]] = None,
    rule_trace: Optional[dict] = None,
    decision: Optional[str] = None,
    missing_information: Optional[list[str]] = None,
) -> RagResponse:
    return RagResponse(
        query=request.query,
        answer_language=language,  # type: ignore[arg-type]
        outcome=outcome,  # type: ignore[arg-type]
        answer=answer,
        sections=sections or [],
        message=message,
        answer_scope=scope,  # type: ignore[arg-type]
        citations=citations or [],
        evidence=evidence or [],
        safety_disclosures=[SafetyDisclosure(**d) for d in (disclosures or [])],
        advisory_status=advisory_status,  # type: ignore[arg-type]
        rule_findings=rule_findings or [],
        rule_trace=rule_trace or {"evaluated": False},
        decision=decision,
        missing_information=missing_information or [],
        confidence=confidence,
        confidence_label=ev.confidence_label(confidence),
        confidence_components=components,
        classification=classification,
        model_versions=model_versions,
    )


def answer_query(
    request: RagRequest,
    *,
    store: Optional[VectorStore] = None,
    bundle: Optional[KnowledgeBundle] = None,
) -> RagResponse:
    """
    Run the full pipeline for one query.

    `store` and `bundle` are injectable so tests can run without a database; the
    defaults are the Phase 5 Postgres store and the configured repository.
    """
    bundle = bundle or get_repository_bundle()
    store = store or get_vector_store()

    classification = classify_query(request.query)
    language = _resolve_language(request.language, classification.detected_language)
    crop_label = classification.crop.label

    classification_summary = {
        "crop": crop_label,
        "crop_confidence": classification.crop.confidence,
        "crop_status": classification.crop.status,
        "task": classification.task.label,
        "task_confidence": classification.task.confidence,
        "task_status": classification.task.status,
        "safety_topic": classification.safety_topic.label,
        "safety_topic_confidence": classification.safety_topic.confidence,
        "detected_language": classification.detected_language,
        "requires_clarification": classification.requires_clarification,
        "unsupported": classification.unsupported,
        "out_of_scope": classification.out_of_scope,
    }
    model_versions = {
        "classifier": classification.model_version or CLASSIFIER_VERSION_FALLBACK,
        "embedding": get_embedding_provider().model_id,
        "vector_backend": store.backend,
        "generation": "extractive",
    }

    ranked = ev.retrieve_and_rank(
        request.query,
        store=store,
        records=bundle.records,
        crop_label=crop_label,
        sources=bundle.sources,
    )
    retrieval_conf = ev.retrieval_confidence(ranked)
    confidence = ev.combine_confidence(retrieval_conf, classification.crop.confidence)
    components = {
        "retrieval": round(retrieval_conf, 3),
        "classification": round(classification.crop.confidence, 3),
        "ranked_chunks": len(ranked),
        "crop_matched_chunks": len(ev.crop_matched(ranked)),
        "pest_aligned": any(r.pest_aligned for r in ranked),
    }

    outcome, detail, record_id, scope = ev.decide(
        ranked=ranked,
        classification=classification,
        records=bundle.records,
        query=request.query,
    )
    components["decision"] = detail

    if outcome != "answered":
        # The classifier already produced localised text for these.
        if outcome == "needs_clarification" and classification.clarification_message:
            message = classification.clarification_message
        elif outcome in ("out_of_scope", "unsupported_crop") and classification.scope_message:
            message = classification.scope_message
        else:
            message = outcome_message(outcome, language)

        gate_decision = DECISION_BY_GATE_OUTCOME[outcome]
        gate_missing = list(MISSING_FOR_GATE_OUTCOME.get(outcome, []))
        if outcome == "safety_value_not_published":
            topic = classification_summary["safety_topic"]
            if topic in ("phi", "rei", "ppe"):
                gate_missing = [topic]

        return _response(
            request=request,
            language=language,
            outcome=outcome,
            classification=classification_summary,
            confidence=confidence,
            components=components,
            model_versions=model_versions,
            message=message,
            decision=gate_decision,
            missing_information=gate_missing,
            # The gate refused before any record was selected, so no rule could
            # run. Saying so is the difference between "no rule fired" and "the
            # rules were never consulted".
            rule_trace={
                "evaluated": False,
                "reason": "decision_gate_refused_before_record_selection",
                "gate_detail": detail,
                "decision": gate_decision,
                "missing_information": gate_missing,
                "rules_run": [],
            },
        )

    # --- evidence selection ------------------------------------------------
    if scope == "record" and record_id:
        selected = ev.select_record_evidence(
            ranked, record_id=record_id, max_items=request.max_evidence
        )
        record_ids = [record_id]
    else:
        selected = ev.select_crop_evidence(
            ranked, crop_id=crop_label or "", max_records=MAX_CROP_RECORDS
        )
        record_ids = [r.chunk.approved_use_id for r in selected if r.chunk.approved_use_id]
        if not record_ids:
            # Retrieval found nothing for this crop (measured case: a Devanagari
            # query whose nearest chunks belong to other crops). The crop label is
            # still confident, so list the crop's records rather than refuse.
            record_ids = ev.select_crop_records(
                bundle.records, crop_id=crop_label or "", max_records=MAX_CROP_RECORDS
            )

    records = [bundle.records[rid] for rid in record_ids if rid in bundle.records]

    # --- Phase 7: rule engine ----------------------------------------------
    # Runs on the selected records, before a single sentence is composed.
    regulatory_evidence = get_regulatory_evidence()
    verdict = get_rule_engine().evaluate(
        RuleContext(
            crop_label=crop_label,
            records=tuple(records),
            all_records=bundle.records,
            sources=bundle.sources,
            crop_confidence=classification.crop.confidence,
            retrieval_confidence=retrieval_conf,
            top_similarity=max((r.chunk.score for r in ranked), default=0.0),
            # Loaded from the backend evidence manifest only. Nothing in the
            # request can reach this argument: RagRequest forbids extra fields,
            # and no route accepts regulatory evidence. Today the manifest does
            # not exist, so this is empty and the gate stays closed.
            regulatory_verification=regulatory_evidence,
            regulatory_evidence_source="backend_evidence_manifest" if regulatory_evidence else "none",
        )
    )
    rule_findings = verdict.rule_findings(language)
    components["rule_blocked"] = verdict.blocked
    components["rule_actionability"] = verdict.actionability

    if verdict.blocked:
        blocking_outcome = OUTCOME_BY_ACTION[verdict.blocking_action]
        return _response(
            request=request,
            language=language,
            outcome=blocking_outcome,
            classification=classification_summary,
            confidence=confidence,
            components=components,
            model_versions=model_versions,
            message=escalation_message(verdict.blocking_action, language),
            rule_findings=rule_findings,
            rule_trace={**verdict.trace, "evaluated": True},
            decision=verdict.decision,
            missing_information=verdict.missing_information,
        )

    if not records:
        # Reached only when the rules did not already block; kept as a belt-and-
        # braces guard so composition is never handed an empty record list.
        return _response(
            request=request,
            language=language,
            outcome="insufficient_evidence",
            classification=classification_summary,
            confidence=confidence,
            components=components,
            model_versions=model_versions,
            message=outcome_message("insufficient_evidence", language),
            rule_findings=rule_findings,
            rule_trace={**verdict.trace, "evaluated": True},
            decision=verdict.decision,
            missing_information=verdict.missing_information,
        )

    builder = build_answer if scope == "record" else build_crop_answer
    answer, sections, disclosures, _all_published = builder(
        records=records,
        crops=bundle.crops,
        sources=bundle.sources,
        language=language,
    )

    citation_groups = ev.build_citation_map(
        records, bundle.sources, bundle.provenance, selected
    )
    citations = [
        Citation(
            source_id=group["source"].source_id,
            title=group["source"].title,
            authority=group["source"].authority,
            url=group["source"].url,
            retrieved_date=group["source"].retrieved_date,
            reliability_tier=group["source"].reliability_tier,
            verification_status=group["verification_status"],
            provenance_sha256=group["provenance_sha256"],
            chunk_refs=group["chunk_refs"],
            record_ids=group["record_ids"],
        )
        for group in citation_groups
    ]

    # The verdict owns actionability now: any `RequireSafetyFields` finding forces
    # EDUCATIONAL_ONLY, and a blocking finding never reaches this line at all.
    advisory_status = verdict.actionability

    status_by_record = {r.approved_use_id: r.advisory_status for r in records}
    return _response(
        request=request,
        language=language,
        outcome="answered",
        classification=classification_summary,
        confidence=confidence,
        components=components,
        model_versions=model_versions,
        answer=answer,
        sections=sections,
        citations=citations,
        evidence=[
            EvidenceItem(
                chunk_ref=item.chunk.chunk_ref,
                chunk_type=item.chunk.chunk_type,
                score=round(item.chunk.score, 6),
                approved_use_id=item.chunk.approved_use_id,
                advisory_status=status_by_record.get(item.chunk.approved_use_id or ""),
            )
            for item in selected
        ],
        disclosures=disclosures,
        advisory_status=advisory_status,
        scope=scope,
        rule_findings=rule_findings,
        rule_trace={**verdict.trace, "evaluated": True},
        decision=verdict.decision,
        missing_information=verdict.missing_information,
    )


def pipeline_status() -> dict:
    """Small diagnostic view of what the pipeline can currently do."""
    bundle = get_repository_bundle()
    store = get_vector_store()
    from app.classification.labels import MIN_CONFIDENCE, MIN_MARGIN

    try:
        chunks = store.count()
    except Exception:  # noqa: BLE001 - status must not fail the request
        chunks = -1

    return {
        "rule_engine": rule_engine_status(),
        "vector_backend": store.backend,
        "embedding_model": get_embedding_provider().model_id,
        "indexed_chunks": chunks,
        "repository_backend": type(bundle.repository).__name__,
        "classifier_version": _classifier_version(),
        "generation_mode": "extractive",
        "thresholds": {
            "min_chunk_similarity": ev.MIN_CHUNK_SIMILARITY,
            "crop_match_boost": ev.CROP_MATCH_BOOST,
            "crop_mismatch_penalty": ev.CROP_MISMATCH_PENALTY,
            "pest_alignment_weight": ev.PEST_ALIGNMENT_WEIGHT,
            "out_of_scope_confidence_floor": ev.OUT_OF_SCOPE_CONFIDENCE_FLOOR,
            "classifier_min_confidence": MIN_CONFIDENCE,
            "classifier_min_margin": MIN_MARGIN,
        },
    }


def _classifier_version() -> str:
    try:
        from app.classification.model import MODEL_VERSION

        return MODEL_VERSION
    except Exception:  # noqa: BLE001
        return CLASSIFIER_VERSION_FALLBACK
