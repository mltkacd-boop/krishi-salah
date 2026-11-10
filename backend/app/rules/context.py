"""
Phase 7 — the inputs a rule is allowed to see.

`RuleContext` is deliberately narrow. A rule receives the records that were
*selected for the answer*, the sources behind them, and the two confidence
signals the pipeline already computed. It receives no vector store, no embedder,
and no classifier object, so a rule cannot re-run retrieval or invent a new
similarity score to justify itself. Every input needed for an audit is in the
frozen dataclass and can be serialised into the trace.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Optional, Sequence

from app.knowledge_base.models import ApprovedUse, Source
from app.rules.verification import RegulatoryEvidence

SAFETY_FIELD_NAMES = ("phi", "rei", "ppe")

# Values in this knowledge base are free text transcribed from the source
# ("7 days", "not stated", "21"). Only a leading number is ever compared, and it
# is never re-emitted as a recommendation — it is used to detect disagreement.
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class RuleContext:
    """
    Everything the rules are allowed to reason about, and nothing else.

    Field notes:
    * `records` — the records selected for the answer. An empty tuple means no
      record exists for this crop/target, which is what `RequireApprovedPair`
      treats as a blocking absence.
    * `crop_confidence` / `retrieval_confidence` — `None` means the signal was
      not supplied (standalone evaluation), never "zero". The confidence rule
      distinguishes the two.
    * `today` — the only clock a rule may read, injected so the staleness rule is
      testable instead of time-dependent.
    """

    crop_label: Optional[str] = None
    records: tuple[ApprovedUse, ...] = ()
    all_records: Mapping[str, ApprovedUse] = field(default_factory=dict)
    sources: Mapping[str, Source] = field(default_factory=dict)
    target_pest: Optional[str] = None
    crop_confidence: Optional[float] = None
    retrieval_confidence: Optional[float] = None
    top_similarity: Optional[float] = None
    today: date = field(default_factory=date.today)
    # record_id -> performed CIB&RC registration check. Values must be
    # `RegulatoryEvidence` objects (app/rules/verification.py); a boolean or a
    # dict shaped like evidence is ignored by `is_verified`, which fails closed.
    # Nothing in this project has ever queried the registry, so the mapping is
    # empty in production and the regulatory rule fires on every record. It is a
    # field rather than a constant so a future, audited evidence manifest can
    # satisfy the gate, and so tests can prove the rule passes.
    regulatory_verification: Mapping[str, "RegulatoryEvidence"] = field(default_factory=dict)
    # Where the evidence came from, recorded in the trace. "none" in production
    # until a manifest exists; never set from a request.
    regulatory_evidence_source: str = "none"

    def source_for(self, record: ApprovedUse) -> Optional[Source]:
        return self.sources.get(record.source_id)


def first_number(value: Optional[str]) -> Optional[float]:
    """Leading number of a transcribed value, or None. Never guesses a unit."""
    if not value:
        return None
    match = _NUMBER_RE.search(value)
    return float(match.group(1)) if match else None


def safety_profile(record: ApprovedUse) -> dict[str, dict]:
    """
    The per-intervention safety profile a chemical recommendation would need.

    Returns one entry per chemical intervention, each mapping the three safety
    fields to their declared status and (when published) value. Taken from the
    intervention level when it carries its own restrictions, otherwise from the
    record level — the same precedence `ApprovedUse.advisory_status` uses, which
    is why the two implementations must agree (see engine.assert_consistency).
    """
    profile: dict[str, dict] = {}
    for index, intervention in enumerate(record.interventions):
        if intervention.control_type != "chemical":
            continue
        restrictions = intervention.safety_restrictions or record.safety_restrictions
        profile[f"{record.approved_use_id}#{index}"] = {
            name: {
                "status": getattr(restrictions, name).status,
                "value": getattr(restrictions, name).value,
            }
            for name in SAFETY_FIELD_NAMES
        }
    return profile


def missing_safety_fields(record: ApprovedUse) -> list[str]:
    """
    Safety fields that are NOT_PUBLISHED_IN_SOURCE for at least one chemical
    intervention, plus 'dosage' for a chemical intervention with no dose.

    Non-chemical interventions are not evaluated: PHI/REI/PPE do not attach to a
    cultural or biological measure, and treating their absence as a data gap
    would manufacture a finding that has no agronomic meaning.
    """
    missing: list[str] = []
    interactive = [(i, intervention) for i, intervention in enumerate(record.interventions)
                   if intervention.control_type == "chemical"]
    if not interactive:
        return ["chemical_intervention"]

    for _, intervention in interactive:
        if not intervention.dosage:
            if "dosage" not in missing:
                missing.append("dosage")

    profile = safety_profile(record)
    for entry in profile.values():
        for name in SAFETY_FIELD_NAMES:
            if entry[name]["status"] != "PUBLISHED" and name not in missing:
                missing.append(name)
    return missing


def is_fully_published(record: ApprovedUse) -> bool:
    """
    Echo of `ApprovedUse.advisory_status`, stated independently.

    Only the three safety fields count here, exactly like the Pydantic computed
    field: a record whose PHI/REI/PPE are all published is actionable even if a
    dose string is absent (a dose gap is reported by the rule as a separate
    finding, but it is not what the model's actionability bit encodes). Keeping
    the two definitions identical is what lets
    `engine.assert_consistency` compare them and fail loudly instead of drifting.
    """
    profile = safety_profile(record)
    if not profile:
        return False
    return all(
        entry[name]["status"] == "PUBLISHED"
        for entry in profile.values()
        for name in SAFETY_FIELD_NAMES
    )


def normalize_pest(name: Optional[str]) -> str:
    """
    Two records describe the same target only if the names normalise equal.

    Deliberately conservative: "Pink bollworm" and "Pink bollworm / Spiny
    bollworm" stay different, because treating them as one pest would compare
    safety values across two different labels.
    """
    if not name:
        return ""
    lowered = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", name.lower())
    return re.sub(r"\s+", " ", lowered).strip()
