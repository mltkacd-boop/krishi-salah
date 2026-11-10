"""
Phase 7 security audit — can a client open the regulatory gate, or override a
safety decision?

The audit asked four questions, each with its own test class here:

1. Can `regulatory_verification` be supplied, forged or modified from outside?
   No: `RagRequest` and `RuleEvaluateRequest` both set `extra="forbid"`, so a
   request naming the field is rejected with 422 before any handler runs, and no
   query parameter is bound to it. Tested for every plausible spelling.
2. Can anything but trusted backend evidence satisfy the gate? No: `is_verified`
   requires a validated `RegulatoryEvidence` object bound to the same record. A
   boolean, a string, or a dict shaped like evidence fails closed.
3. Can a request parameter override a rule decision, a safety restriction or
   `EDUCATIONAL_ONLY`? No: those are computed response fields. The only caller
   inputs on `/rules/evaluate` are the crop, an optional pest/record filter and
   two confidence numbers, and confidence can only *suppress a warning* — it can
   never make a record actionable, because the safety and evidence gates do not
   read it.
4. Bypass attempts must be tested, not assumed. That is this file.

The tests deliberately assert on outcomes a client can observe: HTTP status,
`outcome`, `advisory_status`, `decision`, and the absence of a value.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.rag.pipeline import KnowledgeBundle, answer_query, reset_bundle_cache, reset_regulatory_evidence
from app.rag.schemas import RagRequest
from app.rules import RuleContext, RuleEngine, is_verified
from app.rules.verification import (
    RegulatoryEvidence,
    RegulatoryEvidenceError,
    load_regulatory_evidence,
)
from app.vector.chunking import build_chunks
from app.vector.store import InMemoryVectorStore

from tests.test_phase7_rules import context, make_record, verified_evidence


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def offline():
    repo = JSONFileKnowledgeBaseRepository()
    store = InMemoryVectorStore()
    store.upsert_chunks(
        build_chunks(repo.list_approved_uses(), repo.list_crops(), repo.list_sources())
    )
    bundle = KnowledgeBundle(
        repository=repo,
        records={r.approved_use_id: r for r in repo.list_approved_uses()},
        crops={c.crop_id: c for c in repo.list_crops()},
        sources={s.source_id: s for s in repo.list_sources()},
        provenance={},
    )
    return store, bundle


@pytest.fixture()
def client(offline, monkeypatch) -> TestClient:
    from app.main import app
    import app.rag.pipeline as pipeline_module

    store, bundle = offline
    monkeypatch.setattr(pipeline_module, "get_repository_bundle", lambda: bundle)
    monkeypatch.setattr(pipeline_module, "get_vector_store", lambda: store)
    reset_bundle_cache()
    reset_regulatory_evidence()
    yield TestClient(app)
    reset_bundle_cache()
    reset_regulatory_evidence()


def ask(offline, query: str, **kwargs):
    store, bundle = offline
    return answer_query(RagRequest(query=query, **kwargs), store=store, bundle=bundle)


# ---------------------------------------------------------------------------
# 1. the field cannot be supplied from outside
# ---------------------------------------------------------------------------
INJECTION_KEYS = [
    "regulatory_verification",
    "regulatory_evidence",
    "regulatory_approved",
    "registry_checked",
    "cibrc_registered",
    "advisory_status",
    "actionability",
    "decision",
    "blocked",
    "blocking_action",
    "rule_findings",
    "usage_policy",
    "safety_restrictions",
    "records",
    "all_records",
    "sources",
    "today",
]


class TestRequestCannotSupplyEvidence:
    @pytest.mark.parametrize("key", INJECTION_KEYS)
    def test_rag_answer_rejects_the_field(self, client, key):
        response = client.post(
            "/rag/answer", json={"query": "pink bollworm in cotton", key: True}
        )
        assert response.status_code == 422, f"{key} was accepted"

    @pytest.mark.parametrize("key", INJECTION_KEYS)
    def test_rules_evaluate_rejects_the_field(self, client, key):
        response = client.post("/rules/evaluate", json={"crop": "cotton", key: True})
        assert response.status_code == 422, f"{key} was accepted"

    def test_evidence_cannot_be_injected_as_a_query_string(self, client):
        """Unknown query params are ignored by FastAPI; assert they change nothing."""
        response = client.post(
            "/rag/answer?regulatory_verification=true&advisory_status=ACTIONABLE_WITH_EVIDENCE",
            json={"query": "pink bollworm in cotton"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["advisory_status"] == "EDUCATIONAL_ONLY"
        assert body["decision"] != "ACTIONABLE_RECOMMENDATION"

    def test_nested_smuggling_is_rejected(self, client):
        """A nested object under an allowed key must not carry evidence either."""
        response = client.post(
            "/rag/answer",
            json={"query": "pink bollworm in cotton", "max_evidence": {"regulatory_verification": True}},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 2. only real, correctly bound evidence satisfies the gate
# ---------------------------------------------------------------------------
class TestForgedEvidenceIsRejected:
    @pytest.mark.parametrize(
        "forged",
        [
            True,
            "yes",
            1,
            {"registry": "CIBRC", "registry_reference": "1234"},
            [{"record_id": "AU-TEST-01"}],
        ],
    )
    def test_non_evidence_values_fail_closed(self, forged):
        assert is_verified({"AU-TEST-01": forged}, "AU-TEST-01") is False

    def test_valid_evidence_passes(self):
        evidence = verified_evidence("AU-TEST-01")
        assert is_verified(evidence, "AU-TEST-01") is True

    def test_evidence_for_another_record_does_not_transfer(self):
        evidence = verified_evidence("AU-TEST-01")
        assert is_verified(evidence, "AU-TEST-02") is False

    def test_mismatched_inner_record_id_is_rejected(self):
        """
        `is_verified` checks the evidence's own record_id, not just the dict key,
        so a manifest entry cannot be re-keyed to cover a different record.
        """
        entry = verified_evidence("AU-TEST-01")["AU-TEST-01"]
        assert is_verified({"AU-TEST-02": entry}, "AU-TEST-02") is False

    def test_future_dated_evidence_is_rejected(self):
        entry = verified_evidence("AU-TEST-01")["AU-TEST-01"].model_copy(
            update={"verified_on": "2099-01-01"}
        )
        assert is_verified({"AU-TEST-01": entry}, "AU-TEST-01") is False

    def test_evidence_cannot_be_constructed_without_a_reference(self):
        with pytest.raises(ValidationError):
            RegulatoryEvidence(
                record_id="AU-TEST-01",
                registry="CIBRC",
                registry_reference="",
                verified_on="2026-10-01",
                evidence_url="https://ppqs.gov.in/x",
                evidence_sha256="a" * 64,
                verified_by="someone",
            )

    def test_evidence_rejects_a_different_registry(self):
        with pytest.raises(ValidationError):
            RegulatoryEvidence(
                record_id="AU-TEST-01",
                registry="some other registry",
                registry_reference="1234",
                verified_on="2026-10-01",
                evidence_url="https://example.org/x",
                evidence_sha256="a" * 64,
                verified_by="someone",
            )

    def test_evidence_is_immutable(self):
        entry = verified_evidence("AU-TEST-01")["AU-TEST-01"]
        with pytest.raises(ValidationError):
            entry.registry_reference = "forged"

    def test_short_sha_is_rejected(self):
        with pytest.raises(ValidationError):
            RegulatoryEvidence(
                record_id="AU-TEST-01",
                registry="CIBRC",
                registry_reference="1234",
                verified_on="2026-10-01",
                evidence_url="https://ppqs.gov.in/x",
                evidence_sha256="abc",
                verified_by="someone",
            )


# ---------------------------------------------------------------------------
# 2b. the manifest loader fails closed
# ---------------------------------------------------------------------------
class TestEvidenceManifest:
    def test_absent_manifest_means_no_evidence(self, tmp_path):
        assert load_regulatory_evidence(tmp_path / "absent.json") == {}

    def test_malformed_manifest_raises_instead_of_partially_trusting(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text('[{"record_id": "AU-TEST-01"}]', encoding="utf-8")
        with pytest.raises(RegulatoryEvidenceError):
            load_regulatory_evidence(path)

    def test_duplicate_entries_are_rejected(self, tmp_path):
        entry = verified_evidence("AU-TEST-01")["AU-TEST-01"].model_dump(mode="json")
        path = tmp_path / "dup.json"
        path.write_text(
            __import__("json").dumps({"verifications": [entry, entry]}), encoding="utf-8"
        )
        with pytest.raises(RegulatoryEvidenceError):
            load_regulatory_evidence(path)

    def test_valid_manifest_is_loaded(self, tmp_path):
        entry = verified_evidence("AU-TEST-01")["AU-TEST-01"].model_dump(mode="json")
        path = tmp_path / "ok.json"
        path.write_text(
            __import__("json").dumps({"verifications": [entry]}), encoding="utf-8"
        )
        loaded = load_regulatory_evidence(path)
        assert set(loaded) == {"AU-TEST-01"}

    def test_the_real_project_manifest_does_not_exist_yet(self):
        """Stated as a test so 'nothing is verified' cannot silently become untrue."""
        loaded = load_regulatory_evidence()
        assert loaded == {}, "a regulatory manifest appeared; re-check the gate expectations"


# ---------------------------------------------------------------------------
# 3. no request parameter overrides a decision
# ---------------------------------------------------------------------------
class TestNoDecisionOverride:
    def test_max_evidence_cannot_change_the_decision(self, client):
        base = client.post(
            "/rag/answer", json={"query": "pink bollworm in cotton", "max_evidence": 1}
        ).json()
        wide = client.post(
            "/rag/answer", json={"query": "pink bollworm in cotton", "max_evidence": 10}
        ).json()
        assert base["decision"] == wide["decision"]
        assert base["advisory_status"] == wide["advisory_status"] == "EDUCATIONAL_ONLY"

    def test_language_cannot_change_the_decision(self, client):
        en = client.post(
            "/rag/answer", json={"query": "pink bollworm in cotton", "language": "en"}
        ).json()
        hi = client.post(
            "/rag/answer", json={"query": "pink bollworm in cotton", "language": "hi"}
        ).json()
        assert en["decision"] == hi["decision"]
        assert en["advisory_status"] == hi["advisory_status"]

    def test_high_caller_confidence_cannot_make_a_record_actionable(self, client):
        """
        `/rules/evaluate` lets a reviewer assert confidence. Even at 1.0 the
        safety and evidence gates still hold, because neither reads confidence.
        """
        body = client.post(
            "/rules/evaluate",
            json={"crop": "cotton", "classifier_confidence": 1.0, "retrieval_confidence": 1.0},
        ).json()
        assert body["actionability"] == "EDUCATIONAL_ONLY"
        assert body["decision"] != "ACTIONABLE_RECOMMENDATION"
        assert "regulatory_approval" in body["missing_information"]

    def test_caller_confidence_cannot_rescue_an_unknown_crop(self, client):
        body = client.post(
            "/rules/evaluate",
            json={"crop": "saffron", "classifier_confidence": 1.0, "retrieval_confidence": 1.0},
        ).json()
        assert body["blocked"] is True
        assert body["decision"] == "ESCALATION_REQUIRED"

    def test_record_filter_cannot_select_an_actionable_record(self, client):
        """Picking any record, by id, still yields EDUCATIONAL_ONLY."""
        ids = [
            r.approved_use_id
            for r in JSONFileKnowledgeBaseRepository().list_approved_uses()
        ]
        for rid in ids:
            body = client.post(
                "/rules/evaluate", json={"crop": "cotton", "record_ids": [rid]}
            ).json()
            assert body["actionability"] == "EDUCATIONAL_ONLY", rid

    def test_a_record_from_another_crop_is_blocked_not_answered(self, client):
        body = client.post(
            "/rules/evaluate",
            json={"crop": "rice", "record_ids": ["AU-COTTON-PINK-BOLLWORM-01"]},
        ).json()
        assert body["blocked"] is True

    def test_repeated_requests_are_stable(self, client):
        """No hidden state: ten identical requests produce one answer."""
        seen = {
            client.post("/rag/answer", json={"query": "termite in wheat"}).json()["decision"]
            for _ in range(10)
        }
        assert len(seen) == 1


# ---------------------------------------------------------------------------
# 3b. the knowledge base is not writable through the API
# ---------------------------------------------------------------------------
class TestKnowledgeBaseIsReadOnly:
    @pytest.mark.parametrize(
        "path",
        ["/knowledge-base/crops", "/knowledge-base/sources", "/knowledge-base/approved-uses"],
    )
    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_write_methods_are_not_routed(self, client, path, method):
        response = client.request(method.upper(), path, json={})
        assert response.status_code in (404, 405), f"{method.upper()} {path} -> {response.status_code}"

    def test_approved_use_status_is_not_settable(self, client):
        """`advisory_status` is a computed field; a body cannot set it."""
        response = client.put(
            "/knowledge-base/approved-uses/AU-COTTON-PINK-BOLLWORM-01",
            json={"advisory_status": "ACTIONABLE_WITH_EVIDENCE"},
        )
        assert response.status_code in (404, 405)
        record = client.get(
            "/knowledge-base/approved-uses/AU-COTTON-PINK-BOLLWORM-01"
        ).json()
        assert record["advisory_status"] == "EDUCATIONAL_ONLY"


# ---------------------------------------------------------------------------
# 4. end-to-end: the answer path itself stays closed
# ---------------------------------------------------------------------------
class TestAnswerPathStaysClosed:
    def test_no_shipped_record_can_be_answered_as_actionable(self, offline):
        store, bundle = offline
        repo = JSONFileKnowledgeBaseRepository()
        for record in repo.list_approved_uses():
            response = answer_query(
                RagRequest(query=f"{record.target_pest_common_name} in {record.crop_id}"),
                store=store,
                bundle=bundle,
            )
            assert response.advisory_status in (None, "EDUCATIONAL_ONLY"), record.approved_use_id
            assert response.decision != "ACTIONABLE_RECOMMENDATION", record.approved_use_id

    def test_the_engine_is_satisfiable_only_when_handed_real_evidence(self):
        """
        Proof that the gate is a gate and not a constant: a validated evidence
        object opens it, and nothing weaker does (tested above). The pipeline
        itself never receives one, because it reads the backend manifest only.
        """
        engine = RuleEngine()
        record = make_record()
        verdict = engine.evaluate(
            context(
                records=[record],
                crop_label="cotton",
                regulatory_verification=verified_evidence(record.approved_use_id),
                regulatory_evidence_source="backend_evidence_manifest",
            )
        )
        # The engine is satisfiable with real evidence (proven above), but the
        # shipped pipeline never receives any: see the manifest test.
        assert verdict.decision == "ACTIONABLE_RECOMMENDATION"
        assert verdict.trace["regulatory_evidence_source"] == "backend_evidence_manifest"

    def test_pipeline_trace_reports_no_evidence_source(self, offline):
        response = ask(offline, "pink bollworm in cotton")
        assert response.rule_trace.get("regulatory_evidence_source") in ("none", None)
        assert response.rule_trace.get("regulatory_evidence_records") == []
