"""
Module C — Knowledge Representation (Phase 3 pilot knowledge base).

Exposes a repository over a small, source-traceable set of pest-management
records for the 5 pilot crops (Rice, Wheat, Maize, Cotton, Tomato).

Phase 5 (DEC-012) adds a PostgreSQL implementation behind the *same* interface.
`get_knowledge_base_repository()` now comes from factory.py and selects the
backend from `KB_REPOSITORY` (default `json`), so nothing that imports from this
package needs to change. See models.py for the anti-fabrication schema design,
json_repository.py for the file loader, postgres_repository.py for the database
loader, and provenance.py for the Phase 3.1 (DEC-010) manifest loader.
"""
from app.knowledge_base.factory import (
    KB_REPOSITORY_ENV_VAR,
    KnowledgeBaseRepositoryUnavailable,
    get_knowledge_base_repository,
    get_repository_info,
    reset_knowledge_base_repository_cache,
)
from app.knowledge_base.json_repository import (
    JSONFileKnowledgeBaseRepository,
    KnowledgeBaseLoadError,
)
from app.knowledge_base.models import ApprovedUse, Crop, Intervention, SafetyField, SafetyRestrictions, Source
from app.knowledge_base.postgres_repository import PostgresKnowledgeBaseError, PostgresKnowledgeBaseRepository
from app.knowledge_base.provenance import ProvenanceManifestError, ProvenanceRecord, load_provenance_manifest
from app.knowledge_base.repository import KnowledgeBaseRepository

__all__ = [
    "ApprovedUse",
    "Crop",
    "Source",
    "Intervention",
    "SafetyField",
    "SafetyRestrictions",
    "KnowledgeBaseRepository",
    "JSONFileKnowledgeBaseRepository",
    "PostgresKnowledgeBaseRepository",
    "PostgresKnowledgeBaseError",
    "KnowledgeBaseLoadError",
    "KnowledgeBaseRepositoryUnavailable",
    "KB_REPOSITORY_ENV_VAR",
    "get_knowledge_base_repository",
    "get_repository_info",
    "reset_knowledge_base_repository_cache",
    "ProvenanceRecord",
    "ProvenanceManifestError",
    "load_provenance_manifest",
]
