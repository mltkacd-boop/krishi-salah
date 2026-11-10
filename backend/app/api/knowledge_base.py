"""
Module C support — read-only Knowledge Base API endpoints.

Phase 3 scope: exposes the pilot knowledge base (crops, sources, approved-use
records) for browsing/verification. This is intentionally read-only and does
NOT implement query classification, retrieval ranking, or rule-engine gating —
those are Modules B, D, and E, scheduled for Phases 4-6. The frontend
Knowledge Base screen can call these endpoints to show real (not hardcoded)
data without waiting for PostgreSQL (DEC-008 known gap) or the later
RAG/classification pipeline.
"""
from fastapi import APIRouter, HTTPException

from app.knowledge_base import ApprovedUse, Crop, Source, get_knowledge_base_repository

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/crops", response_model=list[Crop])
def list_crops() -> list[Crop]:
    repo = get_knowledge_base_repository()
    return repo.list_crops()


@router.get("/sources", response_model=list[Source])
def list_sources() -> list[Source]:
    repo = get_knowledge_base_repository()
    return repo.list_sources()


@router.get("/approved-uses", response_model=list[ApprovedUse])
def list_approved_uses(crop_id: str | None = None) -> list[ApprovedUse]:
    repo = get_knowledge_base_repository()
    return repo.list_approved_uses(crop_id=crop_id)


@router.get("/approved-uses/{approved_use_id}", response_model=ApprovedUse)
def get_approved_use(approved_use_id: str) -> ApprovedUse:
    repo = get_knowledge_base_repository()
    record = repo.get_approved_use(approved_use_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No approved_use record with id '{approved_use_id}'.")
    return record
