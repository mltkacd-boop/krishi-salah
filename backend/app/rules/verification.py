"""
Phase 7 security — what may count as regulatory verification.

THE PROBLEM THIS MODULE SOLVES
------------------------------
The regulatory gate in `R2_REQUIRE_SAFETY_FIELDS` blocks actionability until a
CIB&RC registration check exists for a record. If the gate accepted a boolean, any
code path that could pass `{"AU-COTTON-PINK-BOLLWORM-01": True}` would open it —
and "a code path" includes a future endpoint, a query parameter bound into a
dataclass, or a hand-written test fixture promoted to production. A truthy value
is not evidence.

So the gate accepts only `RegulatoryEvidence`: a fully specified record naming the
registry, the registration reference, the date the check was performed, the URL
the check was performed against, and the SHA-256 of the evidence document. Three
consequences:

1. **A bare boolean, a dict, or a string cannot satisfy the gate.** `is_verified`
   type-checks for `RegulatoryEvidence` and then re-checks identity, registry and
   date. Anything else is treated as absent, which fails closed.
2. **Evidence is bound to a record id.** Evidence for one record cannot open the
   gate for another.
3. **Evidence is loaded from a backend file, never from a request.**
   `load_regulatory_evidence()` reads a git-tracked manifest under
   `knowledge_base/seed_data/`. No HTTP route accepts this data; both request
   models forbid extra fields, so a client cannot even name it.

A malformed manifest raises rather than degrading to "some things are verified":
losing the gate's input silently is exactly how a safety control stops working
without anyone noticing. A *missing* manifest is the honest case that exists today
— it returns no evidence, and no record is actionable.

WHAT THIS DOES NOT DO
---------------------
It does not verify the CIB&RC registry itself. It records that a human performed a
check and where. Cryptographic trust would need a signature key held outside this
process; that is out of scope for the pilot and is stated here rather than implied
by the field names.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVIDENCE_PATH = (
    _REPO_ROOT / "knowledge_base" / "seed_data" / "regulatory_verification.json"
)

# The only registry this project names. A free-text registry field would let
# "some registry" stand in for "the Indian regulator".
REGISTRY_CIBRC = "CIBRC"


class RegulatoryEvidenceError(RuntimeError):
    """The evidence manifest exists but cannot be trusted. Fail closed."""


class RegulatoryEvidence(BaseModel):
    """
    One performed CIB&RC registration check.

    Frozen and `extra="forbid"`: an evidence object cannot be edited after it is
    validated, and a manifest entry cannot smuggle extra fields past review.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1, description="Approved-use record this check covers.")
    registry: str = Field(description="Registry consulted. Only CIBRC is accepted.")
    registry_reference: str = Field(
        min_length=3,
        description="The registration/label reference as printed by the registry. Never a "
        "placeholder: this string is what a reviewer would look up.",
    )
    verified_on: date = Field(description="Date the check was actually performed.")
    evidence_url: str = Field(
        min_length=8,
        description="Registry or label page the reference was read from (http/https).",
    )
    evidence_sha256: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 of the saved evidence document, so the bytes can be re-checked.",
    )
    verified_by: str = Field(min_length=2, description="Person or office that performed the check.")

    @field_validator("registry")
    @classmethod
    def _registry_must_be_cibrc(cls, value: str) -> str:
        if value.strip().upper() != REGISTRY_CIBRC:
            raise ValueError(
                f"registry must be {REGISTRY_CIBRC!r}; the project only references the Indian "
                f"central regulator, got {value!r}"
            )
        return REGISTRY_CIBRC

    @field_validator("evidence_url")
    @classmethod
    def _url_must_be_http(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError(f"evidence_url must be an http(s) URL, got {value!r}")
        return value

    @field_validator("evidence_sha256")
    @classmethod
    def _sha_must_be_hex(cls, value: str) -> str:
        lowered = value.lower()
        if any(ch not in "0123456789abcdef" for ch in lowered):
            raise ValueError("evidence_sha256 must be 64 hex characters")
        return lowered


def is_verified(
    evidence: Mapping[str, object],
    record_id: str,
    *,
    today: Optional[date] = None,
) -> bool:
    """
    True only for validated, correctly bound, non-future evidence for this record.

    The `isinstance` check is the security boundary: a boolean, a dict shaped like
    evidence, or any other truthy object is *not* evidence and never satisfies the
    gate. The remaining checks cover evidence that is real but misapplied.
    """
    entry = evidence.get(record_id)
    if not isinstance(entry, RegulatoryEvidence):
        return False
    if entry.record_id != record_id:
        return False
    if entry.registry != REGISTRY_CIBRC:
        return False
    if not isinstance(entry.registry_reference, str) or not entry.registry_reference.strip():
        return False

    # Re-validate the date here rather than trusting the field. Pydantic validates
    # at construction, but `model_copy(update=...)` produces an instance *without*
    # validation, so a mutated copy can carry a string or an impossible date. The
    # boundary that decides "verified" re-checks what it depends on.
    verified_on = entry.verified_on
    if isinstance(verified_on, str):
        try:
            verified_on = date.fromisoformat(verified_on)
        except ValueError:
            return False
    if not isinstance(verified_on, date):
        return False
    reference_day = today or date.today()
    if verified_on > reference_day:
        return False  # a check cannot have happened in the future
    return True


def load_regulatory_evidence(
    path: Optional[Path] = None,
) -> dict[str, RegulatoryEvidence]:
    """
    Read the backend evidence manifest. Missing file → no evidence (the real state).

    Deliberately does not fall back to "assume verified" on any error, and does not
    accept a path from a request: the only caller is the server-side pipeline.
    """
    manifest_path = Path(path) if path else DEFAULT_EVIDENCE_PATH
    if not manifest_path.exists():
        return {}
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RegulatoryEvidenceError(
            f"regulatory evidence manifest at {manifest_path} could not be read: {exc}"
        ) from exc

    items = raw.get("verifications") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise RegulatoryEvidenceError(
            f"{manifest_path} must contain a list (or an object with a 'verifications' list)."
        )

    evidence: dict[str, RegulatoryEvidence] = {}
    for index, item in enumerate(items):
        try:
            entry = RegulatoryEvidence.model_validate(item)
        except Exception as exc:  # noqa: BLE001 - re-raised with the entry index
            raise RegulatoryEvidenceError(
                f"{manifest_path} entry {index} is not valid regulatory evidence: {exc}"
            ) from exc
        if entry.record_id in evidence:
            raise RegulatoryEvidenceError(
                f"{manifest_path} contains two verifications for {entry.record_id}"
            )
        evidence[entry.record_id] = entry
    return evidence


def evidence_ids(evidence: Mapping[str, RegulatoryEvidence]) -> list[str]:
    """Sorted record ids with evidence, for the audit trace."""
    return sorted(rid for rid in evidence if isinstance(evidence.get(rid), RegulatoryEvidence))
