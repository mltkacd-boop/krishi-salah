"""
Phase 5 (DEC-012) — request/response schemas for vector retrieval.

The response deliberately carries the safety gate with every hit:
`advisory_status` comes from the database view (the Phase 3.1 / DEC-010 rule
computed in SQL), and `is_actionable` is derived from it. There is no code path
in which a caller receives a source-transcribed dosage without also receiving
the fact that the record is EDUCATIONAL_ONLY.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_QUERY_LENGTH = 1000
ChunkType = Literal["approved_use", "intervention", "source"]


class VectorSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    limit: int = Field(default=5, ge=1, le=20)
    chunk_types: Optional[list[ChunkType]] = Field(
        default=None,
        description="Restrict retrieval to these chunk types. None means all.",
    )


class VectorSearchHit(BaseModel):
    chunk_type: ChunkType
    chunk_ref: str
    approved_use_id: Optional[str]
    content: str
    score: float = Field(description="Cosine similarity in [-1, 1]. Higher is closer.")
    advisory_status: Optional[Literal["ACTIONABLE_WITH_EVIDENCE", "EDUCATIONAL_ONLY"]] = Field(
        default=None,
        description="Phase 3.1 gate for the record this chunk belongs to. "
        "Null only for source-level chunks, which carry no recommendation.",
    )
    is_actionable: bool = Field(
        description="True only when advisory_status is ACTIONABLE_WITH_EVIDENCE. "
        "False for every pilot record today, because no source publishes PHI/REI/PPE."
    )


class VectorSearchResponse(BaseModel):
    query: str
    hits: list[VectorSearchHit]
    backend: str = Field(description="'pgvector' or 'array' — what actually served this query.")
    embedding_model: str
    notice: str = Field(
        default=(
            "Retrieved text is source-transcribed educational material, not a recommendation. "
            "A record marked EDUCATIONAL_ONLY must not be presented as a safe, actionable dose."
        ),
        description="Non-negotiable framing returned with every result set.",
    )


class KnowledgeBaseStatusResponse(BaseModel):
    """What is actually serving Module C, and what the vector store can do."""

    repository_backend: Optional[str]
    repository_configured: Optional[str]
    repository_class: Optional[str]
    repository_fallback_reason: Optional[str] = None
    kb_repository_env_var: str
    records: Optional[dict] = None
    vector_store: dict
