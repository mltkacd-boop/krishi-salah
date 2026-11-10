"""
Module C — Knowledge Representation: repository abstraction.

Per Phase 3 Requirement #7 ("Make the knowledge-base layer database-independent
so it can later connect to PostgreSQL"), this module defines an abstract
interface. The Phase 3 concrete implementation (`JSONFileKnowledgeBaseRepository`
in json_repository.py) reads from version-controlled JSON files under
knowledge_base/ and does NOT require PostgreSQL to be running.

A future `PostgresKnowledgeBaseRepository` (Phase 5+, once DEC-008's DB gap is
resolved) can implement the exact same interface — nothing in Modules B/D/E/F
that consumes this repository needs to change, mirroring the DEC-004
LLMProvider pattern already used for Module F.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.knowledge_base.models import ApprovedUse, Crop, Source


class KnowledgeBaseRepository(ABC):
    """Provider-agnostic read interface for the pilot knowledge base."""

    @abstractmethod
    def list_crops(self) -> list[Crop]:
        raise NotImplementedError

    @abstractmethod
    def get_crop(self, crop_id: str) -> Optional[Crop]:
        raise NotImplementedError

    @abstractmethod
    def list_sources(self) -> list[Source]:
        raise NotImplementedError

    @abstractmethod
    def get_source(self, source_id: str) -> Optional[Source]:
        raise NotImplementedError

    @abstractmethod
    def list_approved_uses(self, crop_id: Optional[str] = None) -> list[ApprovedUse]:
        """If crop_id is given, returns only records for that crop."""
        raise NotImplementedError

    @abstractmethod
    def get_approved_use(self, approved_use_id: str) -> Optional[ApprovedUse]:
        raise NotImplementedError
