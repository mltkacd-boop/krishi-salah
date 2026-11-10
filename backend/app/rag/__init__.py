"""
Phase 6 — Retrieval-Augmented Generation over the Phase 3/5 knowledge base.

Public surface:
    answer_query(RagRequest) -> RagResponse     the pipeline
    pipeline_status() -> dict                   what is currently wired up

See evidence.py for why the answer/no-answer decision is made by the classifier
rather than by a similarity threshold (measured, not assumed), and generation.py
for why the composer is extractive.
"""
from app.rag.pipeline import (
    KnowledgeBundle,
    answer_query,
    get_repository_bundle,
    pipeline_status,
    reset_bundle_cache,
)
from app.rag.schemas import RagRequest, RagResponse, RagStatusResponse

__all__ = [
    "RagRequest",
    "RagResponse",
    "RagStatusResponse",
    "KnowledgeBundle",
    "answer_query",
    "get_repository_bundle",
    "reset_bundle_cache",
    "pipeline_status",
]
