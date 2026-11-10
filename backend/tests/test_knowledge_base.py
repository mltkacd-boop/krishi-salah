"""
Phase 3 tests — Knowledge Representation module (Module C).

These tests verify:
1. The seed dataset actually loads and validates against the schema (models.py)
   without requiring PostgreSQL — the DB-independence requirement.
2. Every record enforces the anti-fabrication rules: mandatory safety-field
   status, mandatory verification_note, referential integrity to crops/sources.
3. The schema itself rejects invalid data (missing safety status, dangling
   crop/source references, disallowed verification_status) — proving the
   safeguards are real, not just documentation.
4. The read-only Knowledge Base API endpoints serve the same validated data.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.knowledge_base.json_repository import (
    JSONFileKnowledgeBaseRepository,
    KnowledgeBaseLoadError,
    get_knowledge_base_repository,
)
from app.knowledge_base.models import ApprovedUse, SafetyField, SafetyRestrictions, Source


@pytest.fixture(scope="module")
def repo() -> JSONFileKnowledgeBaseRepository:
    return JSONFileKnowledgeBaseRepository()


# --- 1. Dataset loads and is DB-independent ---


def test_repository_loads_without_any_database_connection(repo):
    """No DB/network calls happen in __init__; a successful construction here
    proves the knowledge-base layer works standalone (Phase 3 Requirement #7)."""
    assert isinstance(repo, JSONFileKnowledgeBaseRepository)


def test_all_five_pilot_crops_present(repo):
    crop_ids = {c.crop_id for c in repo.list_crops()}
    assert crop_ids == {"rice", "wheat", "maize", "cotton", "tomato"}


def test_seed_dataset_is_non_empty_but_small_pilot_scale(repo):
    uses = repo.list_approved_uses()
    assert 1 <= len(uses) <= 50, "Pilot dataset should be small and traceable, not mass-generated."


def test_every_pilot_crop_has_at_least_one_record(repo):
    for crop_id in ("rice", "wheat", "maize", "cotton", "tomato"):
        uses = repo.list_approved_uses(crop_id=crop_id)
        assert len(uses) >= 1, f"No knowledge-base record found for pilot crop '{crop_id}'."


# --- 2. Anti-fabrication / traceability rules ---


def test_every_approved_use_has_a_resolvable_source(repo):
    for au in repo.list_approved_uses():
        source = repo.get_source(au.source_id)
        assert source is not None, f"{au.approved_use_id} references missing source '{au.source_id}'"
        assert source.url.startswith("http"), f"{au.source_id} must have a real URL"
        assert source.retrieved_date, f"{au.source_id} must record when it was fetched"


def test_every_approved_use_has_a_resolvable_crop(repo):
    for au in repo.list_approved_uses():
        assert repo.get_crop(au.crop_id) is not None


def test_every_approved_use_carries_a_verification_note(repo):
    for au in repo.list_approved_uses():
        assert au.verification_status == "VERIFIED_SOURCE_RECOMMENDATION"
        assert len(au.verification_note.strip()) > 20, (
            f"{au.approved_use_id} verification_note is missing or too short to be meaningful."
        )


def test_no_unverified_draft_records_in_served_dataset(repo):
    """The loader's referential-integrity check should already reject
    UNVERIFIED_DRAFT records; this test asserts none slipped through."""
    for au in repo.list_approved_uses():
        assert au.verification_status != "UNVERIFIED_DRAFT"


def test_every_safety_field_has_explicit_status(repo):
    """PHI/REI/PPE must each be explicitly PUBLISHED or NOT_PUBLISHED_IN_SOURCE
    — never silently absent. This is the core 'do not invent safety data' check."""
    for au in repo.list_approved_uses():
        for field_name in ("phi", "rei", "ppe"):
            field = getattr(au.safety_restrictions, field_name)
            assert field.status in ("PUBLISHED", "NOT_PUBLISHED_IN_SOURCE")
            if field.status == "PUBLISHED":
                assert field.value, f"{au.approved_use_id}.{field_name} is PUBLISHED but has no value"
            else:
                assert field.note, (
                    f"{au.approved_use_id}.{field_name} is NOT_PUBLISHED_IN_SOURCE but has no "
                    f"explanatory note — a safety gap must never be silent."
                )


def test_every_intervention_has_a_description(repo):
    for au in repo.list_approved_uses():
        assert len(au.interventions) >= 1, f"{au.approved_use_id} has no interventions recorded."
        for interv in au.interventions:
            assert interv.description.strip()


def test_every_source_reliability_tier_is_one_of_known_values(repo):
    allowed = {"national_regulator_ipm_package", "state_agricultural_university"}
    for source in repo.list_sources():
        assert source.reliability_tier in allowed


def test_sources_without_explicit_publication_date_carry_a_note(repo):
    for source in repo.list_sources():
        if source.publication_date is None:
            assert source.publication_date_note, (
                f"{source.source_id} has no publication_date and no explanation why."
            )


# --- 3. Schema actively rejects invalid/fabricated-looking data ---


def test_safety_field_published_without_value_is_rejected():
    with pytest.raises(ValidationError):
        SafetyRestrictions(
            phi=SafetyField(status="PUBLISHED", value=None),
            rei=SafetyField(status="NOT_PUBLISHED_IN_SOURCE", note="not stated"),
            ppe=SafetyField(status="NOT_PUBLISHED_IN_SOURCE", note="not stated"),
        )


def test_safety_field_unpublished_without_note_is_rejected():
    with pytest.raises(ValidationError):
        SafetyRestrictions(
            phi=SafetyField(status="NOT_PUBLISHED_IN_SOURCE", note=None),
            rei=SafetyField(status="NOT_PUBLISHED_IN_SOURCE", note="not stated"),
            ppe=SafetyField(status="NOT_PUBLISHED_IN_SOURCE", note="not stated"),
        )


def test_source_with_non_http_url_is_rejected():
    with pytest.raises(ValidationError):
        Source(
            source_id="SRC-BAD-01",
            title="Bad source",
            authority="Nobody",
            url="not-a-url",
            retrieved_date="2026-11-02",
            geography="India",
            reliability_tier="state_agricultural_university",
        )


def test_approved_use_with_disallowed_verification_status_is_rejected():
    with pytest.raises(ValidationError):
        ApprovedUse(
            approved_use_id="AU-FAKE-01",
            crop_id="rice",
            target_pest_common_name="Fake pest",
            interventions=[{"control_type": "chemical", "description": "x"}],
            safety_restrictions={
                "phi": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                "rei": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                "ppe": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
            },
            source_id="SRC-TNAU-RICE-STEMBORER-01",
            verification_status="APPROVED",  # not an allowed literal value
            verification_note="This should never be accepted.",
        )


def test_repository_rejects_dangling_crop_reference(tmp_path: Path):
    _write_minimal_valid_fixture(tmp_path)
    broken = json.loads((tmp_path / "approved_uses.json").read_text(encoding="utf-8"))
    broken[0]["crop_id"] = "no-such-crop"
    (tmp_path / "approved_uses.json").write_text(json.dumps(broken), encoding="utf-8")

    with pytest.raises(KnowledgeBaseLoadError):
        JSONFileKnowledgeBaseRepository(seed_data_dir=tmp_path)


def test_repository_rejects_dangling_source_reference(tmp_path: Path):
    _write_minimal_valid_fixture(tmp_path)
    broken = json.loads((tmp_path / "approved_uses.json").read_text(encoding="utf-8"))
    broken[0]["source_id"] = "SRC-DOES-NOT-EXIST"
    (tmp_path / "approved_uses.json").write_text(json.dumps(broken), encoding="utf-8")

    with pytest.raises(KnowledgeBaseLoadError):
        JSONFileKnowledgeBaseRepository(seed_data_dir=tmp_path)


def test_repository_raises_clear_error_on_missing_file(tmp_path: Path):
    with pytest.raises(KnowledgeBaseLoadError):
        JSONFileKnowledgeBaseRepository(seed_data_dir=tmp_path)


def _write_minimal_valid_fixture(tmp_path: Path) -> None:
    (tmp_path / "crops.json").write_text(
        json.dumps([{"crop_id": "rice", "crop_name": "Rice", "crop_category": "cereal"}]),
        encoding="utf-8",
    )
    (tmp_path / "sources.json").write_text(
        json.dumps(
            [
                {
                    "source_id": "SRC-X-01",
                    "title": "Test source",
                    "authority": "Test authority",
                    "url": "https://example.gov.in/test",
                    "publication_date": None,
                    "publication_date_note": "test fixture",
                    "retrieved_date": "2026-11-02",
                    "geography": "India",
                    "reliability_tier": "state_agricultural_university",
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "approved_uses.json").write_text(
        json.dumps(
            [
                {
                    "approved_use_id": "AU-X-01",
                    "crop_id": "rice",
                    "target_pest_common_name": "Test pest",
                    "interventions": [{"control_type": "chemical", "description": "test"}],
                    "safety_restrictions": {
                        "phi": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                        "rei": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                        "ppe": {"status": "NOT_PUBLISHED_IN_SOURCE", "note": "n/a"},
                    },
                    "source_id": "SRC-X-01",
                    "verification_status": "VERIFIED_SOURCE_RECOMMENDATION",
                    "verification_note": "Test fixture record for referential-integrity tests.",
                }
            ]
        ),
        encoding="utf-8",
    )


# --- 4. API endpoints serve the same validated data ---


def test_api_list_crops_returns_five_pilot_crops():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/knowledge-base/crops")
    assert resp.status_code == 200
    crop_ids = {c["crop_id"] for c in resp.json()}
    assert crop_ids == {"rice", "wheat", "maize", "cotton", "tomato"}


def test_api_list_approved_uses_filtered_by_crop():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/knowledge-base/approved-uses", params={"crop_id": "wheat"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert all(item["crop_id"] == "wheat" for item in body)


def test_api_get_single_approved_use_includes_safety_restrictions_and_source():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/knowledge-base/approved-uses/AU-WHEAT-APHID-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_id"] == "SRC-NIPHM-DPPQS-WHEAT-01"
    assert body["safety_restrictions"]["phi"]["status"] == "NOT_PUBLISHED_IN_SOURCE"


def test_api_get_unknown_approved_use_returns_404():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/knowledge-base/approved-uses/AU-DOES-NOT-EXIST")
    assert resp.status_code == 404


def test_get_knowledge_base_repository_is_cached_singleton():
    a = get_knowledge_base_repository()
    b = get_knowledge_base_repository()
    assert a is b
