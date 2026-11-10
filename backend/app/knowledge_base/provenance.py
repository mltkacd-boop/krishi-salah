"""
Module C support — Phase 3.1 provenance manifest loader (DEC-010).

Loads `knowledge_base/seed_data/provenance_manifest.json`: a per-record audit
trail produced by actually re-fetching every one of the 8 Phase 3 sources
live (including the 3 that Phase 3 had not yet re-verified: cotton pink
bollworm, maize fall armyworm, and the wheat PDF) and comparing the fetched
text against every value recorded in `approved_uses.json`.

IMPORTANT — what a SHA-256 hash in this manifest does and does NOT prove:
- It proves *integrity*: "the document we hashed is byte-for-byte the one
  whose text we quoted in `verbatim_excerpt`". Anyone can re-fetch the same
  `source_url` and confirm the hash to detect whether the live page has since
  changed.
- It does NOT prove *authenticity* (that the fetched bytes genuinely
  originate from the named government/university authority and were not
  tampered with in transit or by a compromised host) and it does NOT prove
  *regulatory approval* (that CIB&RC has certified the quoted product/crop/
  dose combination). Those are different claims this project has never made
  and this manifest does not start making now. See `verification_status` /
  `verification_note` on each `ApprovedUse` record for the source-verification
  claim this project does make, and DEC-010 for the explicit source-
  verification-vs-regulatory-approval distinction.
- A hash recorded here reflects a specific fetch on `retrieved_date`; it is
  not re-verified automatically on every application start (that would
  require a network call at every repository load, which Phase 3's DB-
  independence design explicitly avoids). Re-running the audit script is a
  manual/CI step, not part of the request-serving path.
"""
import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = _REPO_ROOT / "knowledge_base" / "seed_data" / "provenance_manifest.json"


class ProvenanceRecord(BaseModel):
    """One audited (approved_use_id, source_id) pair."""

    approved_use_id: str
    source_id: str
    source_url: str
    retrieved_date: str
    fetch_method: str
    document_sha256: str
    document_bytes: int
    verbatim_excerpt: str
    verdict: str
    notes: str


class ProvenanceManifestError(RuntimeError):
    """Raised when the manifest file is missing, malformed, or fails validation."""


def load_provenance_manifest(path: Optional[Path] = None) -> list[ProvenanceRecord]:
    manifest_path = Path(path) if path else DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        raise ProvenanceManifestError(f"Provenance manifest not found: {manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProvenanceManifestError(f"Invalid JSON in {manifest_path}: {exc}") from exc
    if not isinstance(raw, list):
        raise ProvenanceManifestError(f"{manifest_path} must contain a JSON array at the top level.")
    try:
        return [ProvenanceRecord.model_validate(item) for item in raw]
    except Exception as exc:  # pydantic ValidationError or similar
        raise ProvenanceManifestError(f"Validation failed while loading {manifest_path}: {exc}") from exc
