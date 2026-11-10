"""
Module C — Knowledge Representation: database-independent concrete repository.

Loads the pilot knowledge base from the version-controlled JSON files under
knowledge_base/seed_data/ (crops.json, sources.json, approved_uses.json).
No database connection is opened or required — this satisfies Phase 3
Requirement #7 (DB-independent KB layer) and Requirement #8 (don't block on
unavailable infrastructure; here, that's PostgreSQL rather than Ollama, but
the same principle applies).

Validation happens at load time via the Pydantic models in models.py, so a
malformed or incomplete record (e.g., a safety field missing its mandatory
status/note) raises immediately with a clear error instead of silently
entering the knowledge base.
"""
import json
from pathlib import Path
from typing import Optional

from app.knowledge_base.models import ApprovedUse, Crop, Source
from app.knowledge_base.repository import KnowledgeBaseRepository

# backend/app/knowledge_base/json_repository.py -> repo root is 4 parents up
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED_DATA_DIR = _REPO_ROOT / "knowledge_base" / "seed_data"


class KnowledgeBaseLoadError(RuntimeError):
    """Raised when the seed data files are missing or fail validation."""


class JSONFileKnowledgeBaseRepository(KnowledgeBaseRepository):
    """Reads and validates the pilot knowledge base from local JSON files."""

    def __init__(self, seed_data_dir: Optional[Path] = None):
        self._dir = Path(seed_data_dir) if seed_data_dir else DEFAULT_SEED_DATA_DIR
        self._crops: dict[str, Crop] = {}
        self._sources: dict[str, Source] = {}
        self._approved_uses: dict[str, ApprovedUse] = {}
        self._load()

    def _load(self) -> None:
        self._crops = {c.crop_id: c for c in self._load_file("crops.json", Crop)}
        self._sources = {s.source_id: s for s in self._load_file("sources.json", Source)}
        self._approved_uses = {
            a.approved_use_id: a for a in self._load_file("approved_uses.json", ApprovedUse)
        }
        self._validate_referential_integrity()

    def _load_file(self, filename: str, model) -> list:
        path = self._dir / filename
        if not path.exists():
            raise KnowledgeBaseLoadError(f"Required knowledge-base file not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseLoadError(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(raw, list):
            raise KnowledgeBaseLoadError(f"{path} must contain a JSON array at the top level.")
        try:
            return [model.model_validate(item) for item in raw]
        except Exception as exc:  # pydantic ValidationError or similar
            raise KnowledgeBaseLoadError(f"Validation failed while loading {path}: {exc}") from exc

    def _validate_referential_integrity(self) -> None:
        """
        Fails loudly if any approved_use references a crop_id or source_id that
        doesn't exist, and if any record claims a verification_status this
        Phase-3 pilot does not actually support. This is deliberately strict:
        a dangling reference or an un-reviewed status must never silently
        enter the served knowledge base.
        """
        errors = []
        for au in self._approved_uses.values():
            if au.crop_id not in self._crops:
                errors.append(f"{au.approved_use_id}: unknown crop_id '{au.crop_id}'")
            if au.source_id not in self._sources:
                errors.append(f"{au.approved_use_id}: unknown source_id '{au.source_id}'")
            if au.verification_status != "VERIFIED_SOURCE_RECOMMENDATION":
                errors.append(
                    f"{au.approved_use_id}: verification_status is "
                    f"'{au.verification_status}', not 'VERIFIED_SOURCE_RECOMMENDATION' — "
                    f"unverified records must not ship in the served pilot dataset."
                )
        if errors:
            raise KnowledgeBaseLoadError(
                "Knowledge-base referential integrity check failed:\n" + "\n".join(errors)
            )

    # --- KnowledgeBaseRepository interface ---

    def list_crops(self) -> list[Crop]:
        return list(self._crops.values())

    def get_crop(self, crop_id: str) -> Optional[Crop]:
        return self._crops.get(crop_id)

    def list_sources(self) -> list[Source]:
        return list(self._sources.values())

    def get_source(self, source_id: str) -> Optional[Source]:
        return self._sources.get(source_id)

    def list_approved_uses(self, crop_id: Optional[str] = None) -> list[ApprovedUse]:
        values = list(self._approved_uses.values())
        if crop_id is not None:
            values = [a for a in values if a.crop_id == crop_id]
        return values

    def get_approved_use(self, approved_use_id: str) -> Optional[ApprovedUse]:
        return self._approved_uses.get(approved_use_id)


_cached_repository: Optional[JSONFileKnowledgeBaseRepository] = None


def get_knowledge_base_repository() -> JSONFileKnowledgeBaseRepository:
    """
    Factory mirroring the get_llm_provider() / get_settings() pattern already
    used elsewhere in this codebase. A future Phase 5 swap to a
    PostgresKnowledgeBaseRepository would change only this function body.
    """
    global _cached_repository
    if _cached_repository is None:
        _cached_repository = JSONFileKnowledgeBaseRepository()
    return _cached_repository
