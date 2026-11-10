"""
Phase 3.1 tests — Safety and Provenance Audit (DEC-010).

These tests verify the Phase 3.1 deliverables, separately from the Phase 3
tests in test_knowledge_base.py:

1. The provenance manifest loads/validates and covers every (approved_use_id,
   source_id) pair actually present in the seed dataset — including the 3
   sources Phase 3 had not yet re-verified (cotton pink bollworm, maize fall
   armyworm, wheat PDF).
2. Every manifest entry carries a real https(s) URL, a non-empty verbatim
   excerpt, a 64-hex-character SHA-256, and an explicit verdict/notes — a
   hash alone proves integrity, not authenticity or regulatory approval
   (tested explicitly), so the manifest must never omit the human verdict.
3. The F7 "misleading completeness" wording is actually gone from the data,
   not just described as fixed.
4. The F8 schema-hardening gaps found during the Phase 3.1 audit are closed:
   empty interventions rejected, a source missing both publication_date and
   publication_date_note rejected.
5. `advisory_status` (DEC-010 Decision 1) correctly gates every pilot record
   to EDUCATIONAL_ONLY (since 0/9 records have any published safety field)
   and would flip to ACTIONABLE_WITH_EVIDENCE only once every chemical
   intervention's safety profile is fully published.
6. The new optional per-intervention `safety_restrictions` field (DEC-010
   Decision 2) is backward compatible: it defaults to None and is never
   auto-populated from the record-level field.
"""
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.knowledge_base.models import ApprovedUse, Intervention, SafetyRestrictions, Source
from app.knowledge_base.provenance import (
    DEFAULT_MANIFEST_PATH,
    ProvenanceManifestError,
    load_provenance_manifest,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(scope="module")
def repo() -> JSONFileKnowledgeBaseRepository:
    return JSONFileKnowledgeBaseRepository()


@pytest.fixture(scope="module")
def manifest():
    return load_provenance_manifest()


# --- 1. Manifest coverage ---


def test_manifest_loads_without_error():
    records = load_provenance_manifest()
    assert len(records) >= 1


def test_manifest_covers_every_approved_use_record(repo, manifest):
    """Every approved_use_id in the served dataset must have been audited —
    this is what makes Phase 3.1 an actual audit, not a sampled spot-check."""
    audited_ids = {m.approved_use_id for m in manifest}
    served_ids = {au.approved_use_id for au in repo.list_approved_uses()}
    missing = served_ids - audited_ids
    assert not missing, f"These records are served but were never provenance-audited: {missing}"


def test_manifest_covers_every_source(repo, manifest):
    """Every source_id referenced by a served record must appear in the
    manifest at least once (sources shared by 2 records, like the wheat PDF,
    only need one manifest entry per record, not per source)."""
    audited_sources = {m.source_id for m in manifest}
    served_sources = {au.source_id for au in repo.list_approved_uses()}
    missing = served_sources - audited_sources
    assert not missing, f"These sources are referenced but never provenance-audited: {missing}"


def test_manifest_entries_reference_real_approved_use_and_source_ids(repo, manifest):
    crop_use_ids = {au.approved_use_id for au in repo.list_approved_uses()}
    source_ids = {s.source_id for s in repo.list_sources()}
    for m in manifest:
        assert m.approved_use_id in crop_use_ids, f"Manifest references unknown record {m.approved_use_id}"
        assert m.source_id in source_ids, f"Manifest references unknown source {m.source_id}"


# --- 2. Manifest entry shape: integrity hash + human verdict, never just one ---


def test_every_manifest_entry_has_a_real_url_and_hash(manifest):
    for m in manifest:
        assert m.source_url.startswith("http"), f"{m.approved_use_id}: source_url must be a real URL"
        assert _SHA256_RE.match(m.document_sha256), (
            f"{m.approved_use_id}: document_sha256 must be a 64-hex-char SHA-256 digest, "
            f"got {m.document_sha256!r}"
        )
        assert m.document_bytes > 0


def test_every_manifest_entry_has_a_nonempty_excerpt_and_human_verdict(manifest):
    """A hash proves integrity, not authenticity or regulatory approval — so
    the manifest must always carry a human-written excerpt/verdict alongside
    the hash, never the hash alone."""
    for m in manifest:
        assert len(m.verbatim_excerpt.strip()) > 20, f"{m.approved_use_id}: excerpt too short to be meaningful"
        assert m.verdict.strip(), f"{m.approved_use_id}: verdict must not be empty"
        assert m.notes.strip(), f"{m.approved_use_id}: notes must not be empty"


def test_manifest_file_is_well_formed_json_array():
    raw = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, list) and len(raw) >= 1


def test_manifest_loader_raises_clear_error_on_missing_file(tmp_path: Path):
    with pytest.raises(ProvenanceManifestError):
        load_provenance_manifest(tmp_path / "does_not_exist.json")


def test_manifest_loader_raises_clear_error_on_malformed_entry(tmp_path: Path):
    bad = tmp_path / "bad_manifest.json"
    bad.write_text(json.dumps([{"approved_use_id": "X"}]), encoding="utf-8")  # missing required fields
    with pytest.raises(ProvenanceManifestError):
        load_provenance_manifest(bad)


# --- 3. F7 fixed: no record overstates how much of a source it retained ---


def test_no_record_claims_to_be_an_exact_or_complete_source_grouping():
    """Phase 3 wording like 'recorded here exactly as the source groups them'
    overstated completeness when a record actually kept only a subset of the
    source's listed options (F7). Phase 3.1 replaced every such phrase with
    an explicit option count and an explicit 'subset, not the complete list'
    (or 'includes all N, not a subset') statement."""
    au_path = DEFAULT_MANIFEST_PATH.parent / "approved_uses.json"
    text = au_path.read_text(encoding="utf-8")
    assert "exactly as the source groups them" not in text
    assert "source groups these as interchangeable options" not in text


# --- 4. F8 schema-hardening gaps closed ---


def test_empty_interventions_list_is_rejected():
    with pytest.raises(ValidationError):
        ApprovedUse(
            approved_use_id="AU-FAKE-EMPTY-01",
            crop_id="rice",
            target_pest_common_name="Fake pest",
            interventions=[],  # Phase 3 accepted this; Phase 3.1 rejects it
            safety_restrictions={
                "phi": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                "rei": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                "ppe": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
            },
            source_id="SRC-TNAU-RICE-STEMBORER-01",
            verification_status="VERIFIED_SOURCE_RECOMMENDATION",
            verification_note="Should never validate: zero interventions.",
        )


def test_source_missing_publication_date_and_note_is_rejected():
    with pytest.raises(ValidationError):
        Source(
            source_id="SRC-FAKE-01",
            title="Fake source",
            authority="Nobody",
            url="https://example.gov.in/test",
            publication_date=None,
            publication_date_note=None,  # Phase 3 accepted this; Phase 3.1 rejects it
            retrieved_date="2026-11-03",
            geography="India",
            reliability_tier="state_agricultural_university",
        )


def test_source_missing_publication_date_but_with_note_is_accepted():
    # Sanity check: the new rule only blocks the *silent* gap, not a
    # documented one — this is the real shape used by 7 of the 8 pilot sources.
    s = Source(
        source_id="SRC-FAKE-02",
        title="Fake source",
        authority="Nobody",
        url="https://example.gov.in/test",
        publication_date=None,
        publication_date_note="Page does not state a last-updated date.",
        retrieved_date="2026-11-03",
        geography="India",
        reliability_tier="state_agricultural_university",
    )
    assert s.publication_date is None


# --- 5. advisory_status gating (DEC-010 Decision 1) ---


def test_every_pilot_record_is_educational_only_today(repo):
    """Ground truth as of Phase 3.1: 0 of 9 records have any PUBLISHED safety
    field, so none may be rendered as an actionable recommendation yet."""
    for au in repo.list_approved_uses():
        assert au.advisory_status == "EDUCATIONAL_ONLY", (
            f"{au.approved_use_id} should be EDUCATIONAL_ONLY until a source "
            f"publishes its PHI/REI/PPE values."
        )


def test_advisory_status_becomes_actionable_only_when_fully_published():
    fully_published = {
        "phi": {"status": "PUBLISHED", "value": "7 days"},
        "rei": {"status": "PUBLISHED", "value": "24 hours"},
        "ppe": {"status": "PUBLISHED", "value": "gloves, mask"},
    }
    au = ApprovedUse(
        approved_use_id="AU-TEST-ACTIONABLE-01",
        crop_id="rice",
        target_pest_common_name="Test pest",
        interventions=[
            {
                "control_type": "chemical",
                "description": "test",
                "active_ingredient_and_formulation": "Test AI",
                "dosage": "1 l/acre",
            }
        ],
        safety_restrictions=fully_published,
        source_id="SRC-TNAU-RICE-STEMBORER-01",
        verification_status="VERIFIED_SOURCE_RECOMMENDATION",
        verification_note="Synthetic fixture to test the gate, not a real recommendation.",
    )
    assert au.advisory_status == "ACTIONABLE_WITH_EVIDENCE"


def test_advisory_status_stays_educational_if_any_single_field_unpublished():
    partially_published = {
        "phi": {"status": "PUBLISHED", "value": "7 days"},
        "rei": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "not stated"},
        "ppe": {"status": "PUBLISHED", "value": "gloves"},
    }
    au = ApprovedUse(
        approved_use_id="AU-TEST-GAP-01",
        crop_id="rice",
        target_pest_common_name="Test pest",
        interventions=[{"control_type": "chemical", "description": "test", "dosage": "1 l/acre"}],
        safety_restrictions=partially_published,
        source_id="SRC-TNAU-RICE-STEMBORER-01",
        verification_status="VERIFIED_SOURCE_RECOMMENDATION",
        verification_note="Synthetic fixture: REI still missing, must stay educational-only.",
    )
    assert au.advisory_status == "EDUCATIONAL_ONLY"


def test_advisory_status_uses_intervention_level_override_when_present():
    """A per-intervention safety_restrictions (DEC-010 Decision 2) takes
    precedence over the record-level one for that specific intervention."""
    record_level_unpublished = {
        "phi": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
        "rei": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
        "ppe": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
    }
    intervention_level_published = {
        "phi": {"status": "PUBLISHED", "value": "3 days"},
        "rei": {"status": "PUBLISHED", "value": "12 hours"},
        "ppe": {"status": "PUBLISHED", "value": "gloves, goggles"},
    }
    au = ApprovedUse(
        approved_use_id="AU-TEST-OVERRIDE-01",
        crop_id="rice",
        target_pest_common_name="Test pest",
        interventions=[
            {
                "control_type": "chemical",
                "description": "test",
                "dosage": "1 l/acre",
                "safety_restrictions": intervention_level_published,
            }
        ],
        safety_restrictions=record_level_unpublished,
        source_id="SRC-TNAU-RICE-STEMBORER-01",
        verification_status="VERIFIED_SOURCE_RECOMMENDATION",
        verification_note="Synthetic fixture: per-product override must win over the record-level gap.",
    )
    assert au.advisory_status == "ACTIONABLE_WITH_EVIDENCE"


def test_non_chemical_only_record_is_educational_only():
    au = ApprovedUse(
        approved_use_id="AU-TEST-CULTURAL-01",
        crop_id="wheat",
        target_pest_common_name="Test pest",
        interventions=[{"control_type": "cultural", "description": "Deep ploughing."}],
        safety_restrictions={
            "phi": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
            "rei": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
            "ppe": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
        },
        source_id="SRC-NIPHM-DPPQS-WHEAT-01",
        verification_status="VERIFIED_SOURCE_RECOMMENDATION",
        verification_note="Synthetic fixture: purely cultural record, no pesticide to gate on.",
    )
    assert au.advisory_status == "EDUCATIONAL_ONLY"


# --- 6. Backward compatibility of the new per-intervention field ---


def test_intervention_safety_restrictions_defaults_to_none_and_is_not_auto_populated():
    interv = Intervention(control_type="chemical", description="test", dosage="1 l/acre")
    assert interv.safety_restrictions is None


def test_existing_pilot_interventions_have_no_auto_populated_safety_restrictions(repo):
    """DEC-010 Decision 2 explicitly forbids copying record-level values down
    into interventions. Confirms the Phase 3.1 schema change did not do that
    to the shipped Phase 3 dataset."""
    for au in repo.list_approved_uses():
        for interv in au.interventions:
            assert interv.safety_restrictions is None, (
                f"{au.approved_use_id}: an intervention has non-null safety_restrictions, but no "
                f"source publishes per-product PHI/REI/PPE for this pilot dataset yet."
            )


def test_safety_restrictions_object_is_still_required_at_record_level(repo):
    """Backward compatibility: the pre-existing record-level field is
    untouched and still mandatory, so every old consumer keeps working."""
    for au in repo.list_approved_uses():
        assert au.safety_restrictions is not None
