"""
Module C — PostgreSQL-backed knowledge-base repository (Phase 5, DEC-012).

Implements the *same* `KnowledgeBaseRepository` interface as
`JSONFileKnowledgeBaseRepository`, so nothing in Modules B/D/E/F changes. This is
the swap that `repository.py` predicted in Phase 3 and mirrors the DEC-004
`LLMProvider` pattern.

Design notes
------------
* Rows are mapped back into the existing Pydantic models rather than into a
  parallel set of DTOs. That keeps a single definition of the anti-fabrication
  rules: a database row that violates them cannot be loaded, because Pydantic
  validates it on construction exactly as it does for the JSON files.
* Read queries are grouped (four queries total, no N+1) and assembled in Python.
  With nine pilot records this is both simpler and faster than joins with
  aggregation.
* `advisory_status` is *read from the database view* and compared with the value
  the Pydantic model derives. The two must agree; `assert_advisory_status_consistency()`
  exists so a test (and the importer) can prove it rather than assume it.
* Read-only by design: writes go through the importer
  (`app/db/import_knowledge_base.py`), so the request-serving path cannot mutate
  the knowledge base.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.knowledge_base.models import ApprovedUse, Crop, Intervention, SafetyField, SafetyRestrictions, Source
from app.knowledge_base.repository import KnowledgeBaseRepository


class PostgresKnowledgeBaseError(RuntimeError):
    """Raised when the database cannot serve the knowledge base."""


def _safety_field(status: Optional[str], value: Optional[str], note: Optional[str]) -> SafetyField:
    if status is None:
        raise PostgresKnowledgeBaseError("safety status column is NULL — the schema forbids this")
    return SafetyField(status=status, value=value, note=note)


def _restrictions(prefix: str, row) -> SafetyRestrictions:
    return SafetyRestrictions(
        phi=_safety_field(row[f"{prefix}phi_status"], row[f"{prefix}phi_value"], row[f"{prefix}phi_note"]),
        rei=_safety_field(row[f"{prefix}rei_status"], row[f"{prefix}rei_value"], row[f"{prefix}rei_note"]),
        ppe=_safety_field(row[f"{prefix}ppe_status"], row[f"{prefix}ppe_value"], row[f"{prefix}ppe_note"]),
    )


class PostgresKnowledgeBaseRepository(KnowledgeBaseRepository):
    """Read-only Postgres implementation of the Module C repository interface."""

    def __init__(self, engine: Optional[Engine] = None) -> None:
        if engine is None:
            from app.db.connection import get_engine
            engine = get_engine()
        self._engine = engine

    # --- helpers ----------------------------------------------------------
    def _rows(self, sql: str, params: Optional[dict] = None) -> list:
        try:
            with self._engine.connect() as conn:
                return conn.execute(text(sql), params or {}).mappings().all()
        except Exception as exc:  # noqa: BLE001 - typed error for callers
            raise PostgresKnowledgeBaseError(
                f"knowledge-base query failed: {exc}. "
                "Check DATABASE_URL and that migrations + import have been run."
            ) from exc

    # --- crops ------------------------------------------------------------
    def list_crops(self) -> list[Crop]:
        rows = self._rows(
            "SELECT crop_id, crop_name, crop_category, is_pilot_crop "
            "FROM crops ORDER BY crop_id"
        )
        return [Crop(**dict(r)) for r in rows]

    def get_crop(self, crop_id: str) -> Optional[Crop]:
        rows = self._rows(
            "SELECT crop_id, crop_name, crop_category, is_pilot_crop "
            "FROM crops WHERE crop_id = :crop_id",
            {"crop_id": crop_id},
        )
        return Crop(**dict(rows[0])) if rows else None

    # --- sources ----------------------------------------------------------
    def list_sources(self) -> list[Source]:
        rows = self._rows(
            "SELECT source_id, title, authority, url, publication_date, publication_date_note, "
            "       retrieved_date, geography, reliability_tier, access_note "
            "FROM sources ORDER BY source_id"
        )
        return [Source(**dict(r)) for r in rows]

    def get_source(self, source_id: str) -> Optional[Source]:
        rows = self._rows(
            "SELECT source_id, title, authority, url, publication_date, publication_date_note, "
            "       retrieved_date, geography, reliability_tier, access_note "
            "FROM sources WHERE source_id = :source_id",
            {"source_id": source_id},
        )
        return Source(**dict(rows[0])) if rows else None

    # --- approved uses ----------------------------------------------------
    def _load_approved_uses(self, crop_id: Optional[str] = None) -> list[ApprovedUse]:
        crop_clause = "WHERE crop_id = :crop_id" if crop_id else ""
        params = {"crop_id": crop_id} if crop_id else {}

        use_rows = self._rows(
            "SELECT approved_use_id, crop_id, target_pest_common_name, "
            "       target_pest_scientific_name, economic_threshold_level, source_id, "
            "       verification_status, verification_note "
            f"FROM approved_uses {crop_clause} ORDER BY approved_use_id",
            params,
        )
        if not use_rows:
            return []
        ids = [r["approved_use_id"] for r in use_rows]

        restriction_rows = self._rows(
            "SELECT approved_use_id, phi_status, phi_value, phi_note, "
            "       rei_status, rei_value, rei_note, ppe_status, ppe_value, ppe_note "
            "FROM approved_use_safety_restrictions WHERE approved_use_id = ANY(:ids)",
            {"ids": ids},
        )
        restrictions = {r["approved_use_id"]: r for r in restriction_rows}

        intervention_rows = self._rows(
            "SELECT approved_use_id, ordinal, control_type, description, "
            "       active_ingredient_and_formulation, dosage, dosage_unit_note, "
            "       safety_phi_status, safety_phi_value, safety_phi_note, "
            "       safety_rei_status, safety_rei_value, safety_rei_note, "
            "       safety_ppe_status, safety_ppe_value, safety_ppe_note "
            "FROM interventions WHERE approved_use_id = ANY(:ids) ORDER BY approved_use_id, ordinal",
            {"ids": ids},
        )
        interventions: dict[str, list[Intervention]] = {}
        for row in intervention_rows:
            per_product = None
            if row["safety_phi_status"] is not None:
                per_product = _restrictions("safety_", row)
            interventions.setdefault(row["approved_use_id"], []).append(Intervention(
                control_type=row["control_type"],
                description=row["description"],
                active_ingredient_and_formulation=row["active_ingredient_and_formulation"],
                dosage=row["dosage"],
                dosage_unit_note=row["dosage_unit_note"],
                safety_restrictions=per_product,
            ))

        records: list[ApprovedUse] = []
        for row in use_rows:
            au_id = row["approved_use_id"]
            if au_id not in restrictions:
                raise PostgresKnowledgeBaseError(
                    f"{au_id}: missing approved_use_safety_restrictions row — every record requires "
                    "an explicit PHI/REI/PPE status, so this cannot be defaulted"
                )
            records.append(ApprovedUse(
                approved_use_id=au_id,
                crop_id=row["crop_id"],
                target_pest_common_name=row["target_pest_common_name"],
                target_pest_scientific_name=row["target_pest_scientific_name"],
                economic_threshold_level=row["economic_threshold_level"],
                interventions=interventions.get(au_id, []),
                safety_restrictions=_restrictions("", restrictions[au_id]),
                source_id=row["source_id"],
                verification_status=row["verification_status"],
                verification_note=row["verification_note"],
            ))
        return records

    def list_approved_uses(self, crop_id: Optional[str] = None) -> list[ApprovedUse]:
        return self._load_approved_uses(crop_id)

    def get_approved_use(self, approved_use_id: str) -> Optional[ApprovedUse]:
        records = self._load_approved_uses()
        for record in records:
            if record.approved_use_id == approved_use_id:
                return record
        return None

    # --- extra (not part of the abstract interface) -----------------------
    def list_provenance(self) -> list[dict]:
        """Provenance audit rows (Phase 3.1 / DEC-010), for verification tooling."""
        rows = self._rows(
            "SELECT approved_use_id, source_id, source_url, retrieved_date, fetch_method, "
            "       document_sha256, document_bytes, verbatim_excerpt, verdict, notes "
            "FROM provenance_records ORDER BY approved_use_id"
        )
        return [dict(r) for r in rows]

    def advisory_status_from_view(self) -> dict[str, str]:
        rows = self._rows("SELECT approved_use_id, advisory_status FROM approved_use_advisory_status")
        return {r["approved_use_id"]: r["advisory_status"] for r in rows}

    def assert_advisory_status_consistency(self) -> list[str]:
        """
        Proves the SQL view and the Pydantic rule agree for every stored record.

        These are two independent implementations of the Phase 3.1 gate (SQL for
        query-time filtering, Python for the API response). If they ever
        disagree, one of them would let an incomplete-safety record look
        actionable, so this returns a list of mismatches for tests to assert on
        rather than trusting them to stay in sync.
        """
        from_view = self.advisory_status_from_view()
        mismatches: list[str] = []
        for record in self._load_approved_uses():
            db_status = from_view.get(record.approved_use_id)
            if db_status != record.advisory_status:
                mismatches.append(
                    f"{record.approved_use_id}: view={db_status} model={record.advisory_status}"
                )
        return mismatches
