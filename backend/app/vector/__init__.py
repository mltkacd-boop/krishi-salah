"""
Module D support — vector storage and retrieval (Phase 5, DEC-012).

See embedding.py for the provider abstraction (and an honest statement of what
the default lexical embedder is not), chunking.py for how retrievable chunks are
derived from validated records, and store.py for the PostgreSQL/in-memory
implementations and the search contract that carries `advisory_status` with
every hit.
"""
from app.vector.chunking import ChunkInput, build_chunks
from app.vector.embedding import (
    DEFAULT_MODEL_ID,
    EMBEDDING_DIM,
    EmbeddingProvider,
    HashingEmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
    reset_embedding_provider_cache,
)
from app.vector.store import (
    InMemoryVectorStore,
    PostgresVectorStore,
    RetrievedChunk,
    VectorStore,
    VectorStoreError,
    VectorStoreUnavailableError,
    get_vector_store,
    reset_vector_store_cache,
)

__all__ = [
    "ChunkInput",
    "build_chunks",
    "DEFAULT_MODEL_ID",
    "EMBEDDING_DIM",
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "cosine_similarity",
    "get_embedding_provider",
    "reset_embedding_provider_cache",
    "InMemoryVectorStore",
    "PostgresVectorStore",
    "RetrievedChunk",
    "VectorStore",
    "VectorStoreError",
    "VectorStoreUnavailableError",
    "get_vector_store",
    "reset_vector_store_cache",
]
