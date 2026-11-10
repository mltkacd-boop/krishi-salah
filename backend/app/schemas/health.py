"""
Pydantic response models for health/readiness endpoints (Module G support).

These shapes are consumed directly by the frontend's health service/hook,
so changing a field name here must be mirrored in frontend/src/types/api.ts.
"""
from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: str
    service: str


class DependencyStatus(BaseModel):
    connected: bool
    message: str


class LLMStatus(BaseModel):
    provider: str
    available: bool
    message: str


class ReadinessResponse(BaseModel):
    status: str  # "ready" | "degraded" - computed from real dependency checks, never hardcoded
    database: DependencyStatus
    pgvector: DependencyStatus
    llm: LLMStatus
    supported_languages: list[str]
