"""
FastAPI application entrypoint.

Serves the knowledge base, the query classifier, retrieval, the grounded RAG
answer pipeline and the Phase 7 rule engine, plus health/readiness endpoints and
automatic OpenAPI docs at /docs.

Request path for an advisory question (POST /rag/answer):
  classify -> embed -> retrieve -> re-rank -> filter evidence -> apply rules ->
  compose an extractive answer with citations
No generative model is called, and no route accepts a decision, a safety value
or regulatory evidence from the client.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import classification, health, knowledge_base, rag, retrieval, rules
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("pesticide_advisory")

app = FastAPI(
    title="Safe Pesticide Use Knowledge and Advisory Assistant - Backend",
    description=(
        "Decision-support API over a source-verified knowledge base of nine "
        "agricultural records. Answers are extractive, carry their citations, "
        "and are gated by a deterministic rule engine. Current state: every "
        "record is EDUCATIONAL_ONLY, so no response is an actionable pesticide "
        "recommendation."
    ),
    version="0.9.0-phase9",
)

# The largest legitimate request is a 1000-character question (MAX_QUERY_LENGTH)
# plus JSON framing, so 16 KB is already generous. This runs *before* CORS is
# added, so a 413 still carries CORS headers and the browser shows the real
# reason instead of a cross-origin failure. It reads Content-Length only: a
# chunked body without that header is caught later by Pydantic's max_length.
MAX_REQUEST_BODY_BYTES = 16 * 1024


@app.middleware("http")
async def reject_oversized_requests(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "status_code": 413,
                        "message": (
                            f"Request body larger than {MAX_REQUEST_BODY_BYTES} bytes. "
                            "Questions are limited to 1000 characters."
                        ),
                    }
                },
            )
    return await call_next(request)


# CORS: exact origins from CORS_ORIGINS, defaulting to the two Vite dev-server
# forms. A deployment must name its frontend origin; "*" is refused rather than
# accepted, because this API is unauthenticated and takes free-text input.
_cors_origins = settings.cors_origin_list
if "*" in _cors_origins:
    raise RuntimeError(
        "CORS_ORIGINS='*' is refused: this API is unauthenticated. List the exact "
        "frontend origins instead (e.g. https://your-app.vercel.app)."
    )
if settings.is_production and all("localhost" in o or "127.0.0.1" in o for o in _cors_origins):
    logger.warning(
        "APP_ENV=production but CORS_ORIGINS contains only loopback origins (%s); "
        "the deployed frontend will be blocked.",
        ", ".join(_cors_origins),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # No cookies or client credentials are used by this application, so
    # credentialed CORS is off. Revisit only if an authenticated session is added.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Structured error shape for expected HTTP errors (4xx raised intentionally,
    including Starlette's own routing-level 404 for unmatched paths). Registered
    on Starlette's base HTTPException so it also catches errors raised by the
    router itself, not only fastapi.HTTPException raised in our own code - the
    exception middleware matches by walking the raised exception's MRO upward.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"status_code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches anything unexpected. Logs the real exception server-side but never
    leaks internals (stack trace, query strings, credentials) to the client.
    """
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "status_code": 500,
                "message": "An unexpected server error occurred. See server logs for details.",
            }
        },
    )


app.include_router(health.router, tags=["health"])
app.include_router(knowledge_base.router)
# Phase 4 (Module B). Additive: existing routes above are untouched.
app.include_router(classification.router)
# Phase 5 (Module C/D). Additive: retrieval routes only; the Phase 3 read-only
# knowledge-base routes above keep serving whatever KB_REPOSITORY selects.
app.include_router(retrieval.router)
# Phase 6 (RAG). Additive: new /rag/* routes only.
app.include_router(rag.router)
# Phase 7 (Module E). Additive: /rules/* exposes the same engine that /rag/answer
# already consults, so the gate can be inspected without composing an answer.
app.include_router(rules.router)


@app.get("/")
def root():
    return {
        "message": "Safe Pesticide Use Knowledge and Advisory Assistant - Milestone 1 backend",
        "docs": "/docs",
        "health": "/health",
        "ready": "/health/ready",
    }
