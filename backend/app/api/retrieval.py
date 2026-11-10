"""
Phase 5 (DEC-012) — retrieval-facing endpoints, additive to Phase 3's
read-only knowledge-base routes.

POST /knowledge-base/similar   vector similarity search over the imported KB
GET  /knowledge-base/status    which repository and vector backend is live

Neither endpoint recommends a pesticide. `/similar` returns source-transcribed
chunks plus the record's `advisory_status`, so the caller always sees the
Phase 3.1 gate (EDUCATIONAL_ONLY today for every record). Answer composition,
clarification and refusal remain Phase 6/7 work.
"""
from fastapi import APIRouter, HTTPException

from app.knowledge_base import get_knowledge_base_repository, get_repository_info
from app.schemas.retrieval import (
    KnowledgeBaseStatusResponse,
    VectorSearchHit,
    VectorSearchRequest,
    VectorSearchResponse,
)
from app.vector.store import VectorStoreError, VectorStoreUnavailableError, get_vector_store

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.post("/similar", response_model=VectorSearchResponse)
def similar_chunks(payload: VectorSearchRequest) -> VectorSearchResponse:
    """
    Cosine-similarity search over the knowledge-base chunks.

    Returns 503 when the vector store cannot answer (database down, migrations or
    import not run) rather than an empty list, because an empty list would look
    like "nothing matched" when the truth is "nothing is indexed".
    """
    store = get_vector_store()
    try:
        raw_hits = store.search(
            payload.query,
            limit=payload.limit,
            chunk_types=payload.chunk_types,
        )
        backend = store.backend
    except VectorStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VectorStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    hits = [
        VectorSearchHit(
            chunk_type=hit.chunk_type,
            chunk_ref=hit.chunk_ref,
            approved_use_id=hit.approved_use_id,
            content=hit.content,
            score=round(hit.score, 6),
            advisory_status=hit.advisory_status,
            is_actionable=hit.is_actionable,
        )
        for hit in raw_hits
    ]
    return VectorSearchResponse(
        query=payload.query,
        hits=hits,
        backend=backend,
        embedding_model=raw_hits[0].embedding_model if raw_hits else _embedding_model_id(),
    )


def _embedding_model_id() -> str:
    from app.vector.embedding import get_embedding_provider

    return get_embedding_provider().model_id


@router.get("/status", response_model=KnowledgeBaseStatusResponse)
def knowledge_base_status() -> KnowledgeBaseStatusResponse:
    """Report the live backends. A fallback to JSON is surfaced, never hidden."""
    info = get_repository_info()
    try:
        repository = get_knowledge_base_repository()
        records = {
            "crops": len(repository.list_crops()),
            "sources": len(repository.list_sources()),
            "approved_uses": len(repository.list_approved_uses()),
        }
    except Exception as exc:  # noqa: BLE001 - status endpoint must not 500
        records = {"error": str(exc)}

    store = get_vector_store()
    try:
        vector_info = {"backend": store.backend, "chunks": store.count()}
        if hasattr(store, "storage_detail"):
            vector_info["detail"] = store.storage_detail()
    except Exception as exc:  # noqa: BLE001
        vector_info = {"backend": "unavailable", "error": str(exc)}

    return KnowledgeBaseStatusResponse(
        repository_backend=info.get("active"),
        repository_configured=info.get("configured"),
        repository_class=info.get("repository_class"),
        repository_fallback_reason=info.get("fallback_reason"),
        kb_repository_env_var="KB_REPOSITORY",
        records=records,
        vector_store=vector_info,
    )
