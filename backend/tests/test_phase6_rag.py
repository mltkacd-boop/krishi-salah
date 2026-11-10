"""
Phase 6 tests — the grounded RAG pipeline.

Group A runs with no database at all: the JSON knowledge base plus an in-memory
vector store, so the extraction, ranking and decision logic is always exercised.
Group B covers the HTTP surface. Group C re-runs the same end-to-end path against
the real PostgreSQL store when it is reachable, and skips with a reason otherwise.

The assertions that matter most are negative ones: the pipeline must refuse rather
than answer when the pest is not in the knowledge base, must never emit a PHI/REI/
PPE value no source publishes, must never claim regulatory approval, and must never
report an outcome outside the declared enum.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.rag import evidence as ev
from app.rag.pipeline import KnowledgeBundle, answer_query, reset_bundle_cache
from app.rag.schemas import RAG_OUTCOMES, RagRequest
from app.vector.chunking import build_chunks
from app.vector.store import InMemoryVectorStore

PILOT_CROPS = {"rice", "wheat", "maize", "cotton", "tomato"}


# ---------------------------------------------------------------------------
# offline fixtures (JSON repository + in-memory vectors)
# ---------------------------------------------------------------------------
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
    """Mirror get_repository_bundle(), including the provenance-manifest fallback."""
    from app.knowledge_base.provenance import load_provenance_manifest

    provenance = {
        item.approved_use_id: item.document_sha256[:16]
        for item in load_provenance_manifest()
        if item.document_sha256
    }
    return KnowledgeBundle(
        repository=json_repo,
        records={r.approved_use_id: r for r in json_repo.list_approved_uses()},
        crops={c.crop_id: c for c in json_repo.list_crops()},
        sources={s.source_id: s for s in json_repo.list_sources()},
        provenance=provenance,
    )


@pytest.fixture(scope="module")
def ask(bundle, offline_store):
    def _ask(query: str, **kwargs):
        return answer_query(
            RagRequest(query=query, **kwargs), store=offline_store, bundle=bundle
        )

    return _ask


# ---------------------------------------------------------------------------
# A. retrieval, ranking and grounded assembly
# ---------------------------------------------------------------------------
class TestGrounding:
    def test_answers_from_the_knowledge_base(self, ask):
        response = ask("pink bollworm management in cotton")
        assert response.outcome == "answered"
        assert response.answer_scope == "record"
        # The paragraph is assembled from the record, so its pest name is present.
        assert "Pink bollworm" in response.answer
        assert response.sections, "an answered response must carry structured sections"
        assert response.evidence, "an answered response must cite retrieved chunks"

    def test_every_answer_has_a_citation_with_a_url(self, ask):
        response = ask("fall armyworm in maize")
        assert response.outcome == "answered"
        assert response.citations
        for citation in response.citations:
            assert citation.source_id.startswith("SRC-")
            assert citation.url.startswith("http")
            assert citation.title and citation.authority
            assert isinstance(citation.reliability_tier, str) and citation.reliability_tier

    def test_citation_follows_the_cited_record_not_the_retrieval_hit(self, ask):
        """A crop-level answer must cite the crop's records even if retrieval drifted."""
        response = ask("धान का तना छेदक")
        assert response.outcome == "answered"
        cited_records = [rid for c in response.citations for rid in c.record_ids]
        assert "AU-RICE-YELLOW-STEM-BORER-01" in cited_records
        assert all(rid.startswith("AU-RICE-") for rid in cited_records)

    def test_pest_name_alignment_beats_raw_similarity(self, bundle, offline_store):
        """
        Within cotton, three records tie on crop boost. The rare token decides.

        Measured during development: raw similarity ranked "Spotted bollworm /
        Spiny bollworm" first for a pink-bollworm query, because "bollworm" is
        shared by all three.
        """
        ranked = ev.retrieve_and_rank(
            "pink bollworm in cotton", store=offline_store, records=bundle.records,
            crop_label="cotton",
        )
        aligned = [r for r in ranked if r.pest_aligned]
        assert aligned[0].chunk.approved_use_id == "AU-COTTON-PINK-BOLLWORM-01"
        assert aligned[0].adjusted_score > max(
            r.adjusted_score for r in ranked
            if r.chunk.approved_use_id == "AU-COTTON-SPOTTED-SPINY-BOLLWORM-01"
        )

    def test_spotted_bollworm_query_does_not_return_pink_bollworm(self, ask):
        response = ask("spotted bollworm on cotton")
        assert response.outcome == "answered"
        assert response.evidence[0].approved_use_id == "AU-COTTON-SPOTTED-SPINY-BOLLWORM-01"

    def test_query_embedding_is_generated_by_the_configured_provider(self, ask):
        response = ask("termite in wheat")
        assert response.model_versions["embedding"]
        assert response.model_versions["vector_backend"] == "memory"
        assert response.model_versions["generation"] == "extractive"

    def test_unattributable_chunks_are_filtered_out(self, bundle, offline_store):
        """A record whose source is missing must not become evidence."""
        without_sources = ev.retrieve_and_rank(
            "pink bollworm in cotton", store=offline_store, records=bundle.records,
            crop_label="cotton", sources={},
        )
        assert without_sources == []
        with_sources = ev.retrieve_and_rank(
            "pink bollworm in cotton", store=offline_store, records=bundle.records,
            crop_label="cotton", sources=bundle.sources,
        )
        assert with_sources
        assert all(
            bundle.records[r.chunk.approved_use_id].source_id in bundle.sources
            for r in with_sources
        )

    def test_classifier_context_is_reported_and_used(self, ask):
        response = ask("yellow stem borer control in rice")
        assert response.classification["crop"] == "rice"
        assert response.classification["crop_confidence"] > 0
        assert response.classification["safety_topic"]
        assert response.confidence_components["crop_matched_chunks"] >= 1


class TestRefusals:
    """Nothing may be answered that the knowledge base cannot support."""

    def test_unknown_pest_is_refused(self, ask):
        response = ask("whitefly on cotton")
        assert response.outcome == "insufficient_evidence"
        assert response.answer is None
        assert response.citations == []

    def test_disease_question_is_refused_not_answered_with_an_insect(self, ask):
        """
        "bacterial blight" is a disease; the only rice records are insects.

        Before crop words were removed from the pest vocabulary this aligned to
        "Rice Leaf Folder" on the word "rice" and answered confidently.
        """
        response = ask("bacterial blight in rice")
        assert response.outcome == "insufficient_evidence"
        assert response.answer is None

    def test_phi_question_never_produces_a_number(self, ask):
        response = ask("how long before I can harvest after spraying cotton")
        assert response.outcome == "safety_value_not_published"
        assert response.answer is None
        assert response.message
        assert not any(ch.isdigit() for ch in response.message)

    def test_ppe_question_never_produces_equipment_values(self, ask):
        response = ask("what PPE do I need for spraying tomato")
        assert response.outcome == "safety_value_not_published"
        assert response.answer is None

    def test_unpublished_safety_fields_are_reported_not_invented(self, ask):
        response = ask("pink bollworm management in cotton")
        assert response.outcome == "answered"
        assert response.safety_disclosures
        for disclosure in response.safety_disclosures:
            if disclosure.status != "PUBLISHED":
                assert disclosure.value is None

    def test_regulatory_question_is_escalated(self, ask):
        response = ask("is chlorpyriphos approved for rice in India")
        assert response.outcome == "no_regulatory_verification"
        assert response.answer is None

    def test_out_of_domain_question_is_declined(self, ask):
        response = ask("how do I fix my tractor engine")
        assert response.outcome == "out_of_scope"
        assert response.answer is None

    def test_non_pilot_crop_is_declined(self, ask):
        response = ask("saffron pest control")
        assert response.outcome == "unsupported_crop"
        assert response.answer is None

    def test_vague_query_asks_for_clarification(self, ask):
        response = ask("what is the mandi price of rice today")
        assert response.outcome in ("needs_clarification", "out_of_scope")
        assert response.answer is None

    def test_a_pest_name_alone_still_answers(self, ask):
        """The classifier flags an underspecified task; a unique record resolves it."""
        response = ask("wheat termite")
        assert response.outcome == "answered"
        assert response.evidence[0].approved_use_id == "AU-WHEAT-TERMITE-01"


class TestBilingual:
    def test_hindi_query_is_answered_at_crop_scope(self, ask):
        """
        The lexical embedder cannot match Devanagari to English pest names, so the
        pipeline lists the crop's records instead of guessing a pest match.
        """
        response = ask("कपास में गुलाबी सुंडी")
        assert response.outcome == "answered"
        assert response.answer_scope == "crop"
        assert response.answer_language == "hi"
        assert response.citations

    def test_hindi_crop_answer_names_all_three_cotton_records(self, ask):
        response = ask("कपास में गुलाबी सुंडी")
        cited = {rid for c in response.citations for rid in c.record_ids}
        assert cited == {
            "AU-COTTON-AMERICAN-BOLLWORM-01",
            "AU-COTTON-PINK-BOLLWORM-01",
            "AU-COTTON-SPOTTED-SPINY-BOLLWORM-01",
        }

    def test_hindi_answer_body_is_in_devanagari(self, ask):
        response = ask("धान का तना छेदक")
        assert response.answer_language == "hi"
        body = response.answer or ""
        devanagari = sum(1 for ch in body if "\u0900" <= ch <= "\u097f")
        assert devanagari > len(body) * 0.3

    def test_hindi_crop_name_is_localised(self, ask):
        response = ask("धान का तना छेदक")
        assert response.answer is not None
        assert "धान" in response.answer

    def test_language_can_be_forced(self, ask):
        response = ask("pink bollworm management in cotton", language="hi")
        assert response.answer_language == "hi"

    def test_hindi_refusal_is_localised(self, ask):
        response = ask("कपास पर सफेद मक्खी")
        if response.outcome != "answered":
            assert any("\u0900" <= ch <= "\u097f" for ch in (response.message or ""))


class TestContract:
    def test_outcome_is_always_in_the_declared_enum(self, ask):
        probes = [
            "pink bollworm in cotton",
            "whitefly on cotton",
            "how long before harvest after spraying cotton",
            "is chlorpyriphos approved for rice",
            "how do I fix my tractor engine",
            "saffron pest control",
            "hello",
            "कपास में गुलाबी सुंडी",
        ]
        for query in probes:
            response = ask(query)
            assert response.outcome in RAG_OUTCOMES, (query, response.outcome)

    def test_educational_only_is_preserved(self, ask):
        for query in ("pink bollworm management in cotton", "whitefly on cotton"):
            response = ask(query)
            assert response.usage_policy["educational_only"] is True
            assert response.usage_policy["is_pesticide_recommendation"] is False
            assert response.advisory_status in (None, "EDUCATIONAL_ONLY")

    def test_generation_is_extractive_and_citations_are_mandatory(self, ask):
        response = ask("fall armyworm in maize")
        assert response.generation_mode == "extractive"
        assert response.usage_policy["must_show_citations"] is True

    def test_confidence_is_bounded_and_labelled(self, ask):
        for query in ("pink bollworm management in cotton", "whitefly on cotton", "hello"):
            response = ask(query)
            assert 0.0 <= response.confidence <= 0.95
            assert response.confidence_label in ("low", "medium", "high")

    def test_no_answered_response_lacks_evidence(self, ask):
        for query in ("pink bollworm management in cotton", "termite in wheat", "टमाटर"):
            response = ask(query)
            if response.outcome == "answered":
                assert response.evidence and response.citations

    def test_request_validation(self):
        with pytest.raises(ValidationError):
            RagRequest(query="")
        with pytest.raises(ValidationError):
            RagRequest(query="ok", max_evidence=0)
        with pytest.raises(ValidationError):
            RagRequest(query="ok", max_evidence=11)

    def test_deterministic_for_the_same_query(self, ask):
        first = ask("fall armyworm in maize")
        second = ask("fall armyworm in maize")
        assert first.outcome == second.outcome
        assert first.answer == second.answer
        assert first.confidence == second.confidence


# ---------------------------------------------------------------------------
# B. HTTP surface
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
    def test_answer_endpoint_returns_the_full_contract(self, client):
        response = client.post("/rag/answer", json={"query": "pink bollworm in cotton"})
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "answered"
        assert body["generation_mode"] == "extractive"
        assert body["usage_policy"]["educational_only"] is True
        assert body["citations"]
        assert body["answer"]

    def test_refusal_is_a_200_with_an_outcome_not_an_error(self, client):
        response = client.post("/rag/answer", json={"query": "whitefly on cotton"})
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "insufficient_evidence"
        assert body["answer"] is None

    def test_empty_query_is_rejected(self, client):
        assert client.post("/rag/answer", json={"query": ""}).status_code == 422

    def test_unknown_field_is_rejected(self, client):
        response = client.post("/rag/answer", json={"query": "termite", "temperature": 0})
        assert response.status_code == 422

    def test_status_endpoint_reports_backends(self, client):
        response = client.get("/rag/status")
        assert response.status_code == 200
        body = response.json()
        assert body["generation_mode"] == "extractive"
        assert body["embedding_model"]
        assert body["thresholds"]["min_chunk_similarity"] >= 0

    def test_unavailable_vector_store_returns_503(self, client, monkeypatch):
        from app.vector.store import VectorStoreUnavailableError
        import app.rag.pipeline as pipeline_module

        def _boom():
            raise VectorStoreUnavailableError("database down")

        monkeypatch.setattr(pipeline_module, "get_vector_store", _boom)
        response = client.post("/rag/answer", json={"query": "termite in wheat"})
        assert response.status_code == 503
        assert "database down" in response.json()["error"]["message"]

    def test_missing_classifier_returns_503(self, client, monkeypatch):
        from app.classification.service import ClassifierUnavailableError
        import app.rag.pipeline as pipeline_module

        def _boom(_query):
            raise ClassifierUnavailableError("artifact missing")

        monkeypatch.setattr(pipeline_module, "classify_query", _boom)
        response = client.post("/rag/answer", json={"query": "termite in wheat"})
        assert response.status_code == 503

    def test_existing_routes_still_work(self, client):
        for path in ("/health", "/knowledge-base/crops", "/rag/status"):
            assert client.get(path).status_code == 200, path
        assert "/rag/answer" in str(client.get("/openapi.json").json()["paths"])


# ---------------------------------------------------------------------------
# C. against the real PostgreSQL store, when it is reachable
# ---------------------------------------------------------------------------
def _database_ready() -> tuple[bool, str]:
    try:
        from sqlalchemy import text

        from app.db.connection import check_database_connection, get_engine

        ok, message = check_database_connection()
        if not ok:
            return False, message
        with get_engine().connect() as conn:
            chunks = conn.execute(text("SELECT count(*) FROM embeddings")).scalar()
        if not chunks:
            return False, "kb_chunks is empty (run import_knowledge_base.py)"
        return True, f"{chunks} chunks"
    except Exception as exc:  # noqa: BLE001 - reported as a skip reason
        return False, f"{type(exc).__name__}: {exc}"


_DB_READY, _DB_REASON = _database_ready()
requires_pg = pytest.mark.skipif(not _DB_READY, reason=f"PostgreSQL not ready: {_DB_REASON}")


@requires_pg
class TestPostgresPipeline:
    def test_full_pipeline_over_the_real_store(self):
        response = answer_query(RagRequest(query="pink bollworm management in cotton"))
        assert response.outcome == "answered"
        assert response.model_versions["vector_backend"] in ("array", "pgvector")
        assert response.citations
        assert response.citations[0].provenance_sha256, "provenance digest must be attached"

    def test_refusals_survive_the_real_store(self):
        assert answer_query(RagRequest(query="whitefly on cotton")).outcome == (
            "insufficient_evidence"
        )
        assert answer_query(
            RagRequest(query="is chlorpyriphos approved for rice")
        ).outcome == "no_regulatory_verification"

    def test_hindi_crop_answer_over_the_real_store(self):
        response = answer_query(RagRequest(query="कपास में गुलाबी सुंडी"))
        assert response.outcome == "answered"
        assert response.answer_scope == "crop"
        assert len(response.citations) >= 1
