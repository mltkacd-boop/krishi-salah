"""
Module B — classification API endpoints (Phase 4).

Additive only: these routes are registered alongside the existing health and
knowledge-base routers, and no existing route, path or response shape changes.

Scope boundary carried in the response body (not just in documentation):
a classification result is an *intent label*. It approves no pesticide
recommendation and cannot lift the Phase 3.1 `EDUCATIONAL_ONLY` gate — see
`app.classification.schemas.SafetyPolicy`, which every response includes.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.classification.schemas import ClassifyRequest, ClassifyResponse, ModelInfoResponse
from app.classification.service import (
    ClassifierUnavailableError,
    classify_query,
    get_model_info,
)

logger = logging.getLogger("pesticide_advisory.classification")

router = APIRouter(prefix="/classification", tags=["classification"])


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    summary="Classify an agricultural query into crop, task and safety topic",
    responses={
        200: {"description": "Structured classification with per-dimension confidence."},
        422: {"description": "Request validation failed (empty, blank or over-long query)."},
        503: {"description": "The classification model artifact is not available."},
    },
)
def classify(payload: ClassifyRequest) -> ClassifyResponse:
    """
    Classify one free-text query.

    Returns all three dimensions separately with a confidence score and an
    explicit status per dimension. A low-confidence dimension is reported as
    `ambiguous` with `requires_clarification=true` and a ready-to-show question
    — it is never silently resolved into a guess.

    This endpoint does **not** retrieve knowledge, apply safety rules, or
    generate advice; those are Modules D-F.
    """
    try:
        return classify_query(payload.query)
    except ClassifierUnavailableError as exc:
        # Honest failure: never fall back to a made-up prediction.
        logger.error("Classification request failed: model unavailable (%s)", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "The classification model is not available on this server. "
                "It must be trained and its artifact deployed before queries can be classified."
            ),
        ) from exc


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Model identity, label taxonomy and decision thresholds",
    responses={503: {"description": "The classification model artifact is not available."}},
)
def model_info() -> ModelInfoResponse:
    """
    Verifiability endpoint: which model version is loaded, what labels it can
    emit, and what thresholds decide an abstention. Intended for auditors and
    developers — the frontend does not surface these internals to end users.
    """
    try:
        return get_model_info()
    except ClassifierUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
