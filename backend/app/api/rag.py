"""
Phase 6 API — grounded RAG answers.

POST /rag/answer   full pipeline; 503 when the knowledge base or vector store is
                   unavailable (never a fabricated answer)
GET  /rag/status   which backends and thresholds are live

The response is advisory text with citations, not a pesticide recommendation.
`usage_policy` and `outcome` make that machine-checkable.
"""
from fastapi import APIRouter, HTTPException

from app.classification.service import ClassifierUnavailableError
from app.knowledge_base.factory import KnowledgeBaseRepositoryUnavailable
from app.rag.pipeline import answer_query, pipeline_status
from app.rag.schemas import RagRequest, RagResponse, RagStatusResponse
from app.vector.store import VectorStoreError, VectorStoreUnavailableError

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/answer", response_model=RagResponse)
def rag_answer(payload: RagRequest) -> RagResponse:
    try:
        return answer_query(payload)
    except (VectorStoreUnavailableError, KnowledgeBaseRepositoryUnavailable, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ClassifierUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/status", response_model=RagStatusResponse)
def rag_status() -> RagStatusResponse:
    try:
        return RagStatusResponse(**pipeline_status())
    except Exception as exc:  # noqa: BLE001 - diagnostics endpoint must not 500
        raise HTTPException(status_code=503, detail=f"RAG pipeline unavailable: {exc}") from exc
