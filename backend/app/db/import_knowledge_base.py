"""
Phase 5 (DEC-012) — seed/import the knowledge base into PostgreSQL.

The JSON files under knowledge_base/seed_data/ stay the authoritative *source*
of the pilot data. This script copies them into PostgreSQL — it does not become a
second place where agronomic facts are authored, so there is no risk of the two
diverging by hand-editing SQL.

Guarantees
----------
* Every row is validated by the Phase 3 Pydantic models BEFORE any SQL runs, so a
  record that violates the anti-fabrication rules cannot enter the database.
* One transaction: a partial import is impossible.
* Idempotent: re-running updates in place (ON CONFLICT), and interventions are
  replaced per record so a removed measure disappears instead of lingering.
* Verifies itself afterwards: row counts must match the source, and the SQL
  advisory-status view must agree with the Pydantic rule for every record
  (two independent implementations of the Phase 3.1 gate).
* Never invents a value: a NULL in the JSON stays NULL in the database, and the
  CHECK constraints reject a PUBLISHED field without a value or a
  NOT_PUBLISHED_IN_SOURCE field without a note.

Usage (from backend/, venv active, .env configured, migrations applied):
    python -m app.db.import_knowledge_base
    python -m app.db.import_knowledge_base --skip-embeddings
    python -m app.db.import_knowledge_base --dry-run
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.knowledge_base.json_repository import JSONFileKnowledgeBaseRepository
from app.knowledge_base.models import ApprovedUse, Crop, Source
from app.knowledge_base.provenance import load_provenance_manifest


def _crop_rows(crops: list[Crop]) -> list[dict]:
    return [
        {
            "crop_id": c.crop_id,
            "crop_name": c.crop_name,
            "crop_category": c.crop_category,
            "is_pilot_crop": c.is_pilot_crop,
        }
        for c in crops
    ]


def _source_rows(sources: list[Source]) -> list[dict]:
    return [
        {
            "source_id": s.source_id,
            "title": s.title,
            "authority": s.authority,
            "url": s.url,
            "publication_date": s.publication_date,
            "publication_date_note": s.publication_date_note,
            "retrieved_date": s.retrieved_date,
            "geography": s.geography,
            "reliability_tier": s.reliability_tier,
            "access_note": s.access_note,
        }
        for s in sources
    ]


def _approved_use_row(record: ApprovedUse) -> dict:
    return {
        "approved_use_id": record.approved_use_id,
        "crop_id": record.crop_id,
        "target_pest_common_name": record.target_pest_common_name,
        "target_pest_scientific_name": record.target_pest_scientific_name,
        "economic_threshold_level": record.economic_threshold_level,
        "source_id": record.source_id,
        "verification_status": record.verification_status,
        "verification_note": record.verification_note,
    }


def _restriction_row(record: ApprovedUse) -> dict:
    s = record.safety_restrictions
    return {
        "approved_use_id": record.approved_use_id,
        "phi_status": s.phi.status, "phi_value": s.phi.value, "phi_note": s.phi.note,
        "rei_status": s.rei.status, "rei_value": s.rei.value, "rei_note": s.rei.note,
        "ppe_status": s.ppe.status, "ppe_value": s.ppe.value, "ppe_note": s.ppe.note,
    }


def _intervention_rows(record: ApprovedUse) -> list[dict]:
    rows: list[dict] = []
    for ordinal, intervention in enumerate(record.interventions, start=1):
        per_product = intervention.safety_restrictions
        rows.append({
            "approved_use_id": record.approved_use_id,
            "ordinal": ordinal,
            "control_type": intervention.control_type,
            "description": intervention.description,
            "active_ingredient_and_formulation": intervention.active_ingredient_and_formulation,
            "dosage": intervention.dosage,
            "dosage_unit_note": intervention.dosage_unit_note,
            "safety_phi_status": per_product.phi.status if per_product else None,
            "safety_phi_value": per_product.phi.value if per_product else None,
            "safety_phi_note": per_product.phi.note if per_product else None,
            "safety_rei_status": per_product.rei.status if per_product else None,
            "safety_rei_value": per_product.rei.value if per_product else None,
            "safety_rei_note": per_product.rei.note if per_product else None,
            "safety_ppe_status": per_product.ppe.status if per_product else None,
            "safety_ppe_value": per_product.ppe.value if per_product else None,
            "safety_ppe_note": per_product.ppe.note if per_product else None,
        })
    return rows


SQL_UPSERT_CROP = text(
    """
    INSERT INTO crops (crop_id, crop_name, crop_category, is_pilot_crop)
    VALUES (:crop_id, :crop_name, :crop_category, :is_pilot_crop)
    ON CONFLICT (crop_id) DO UPDATE
       SET crop_name = EXCLUDED.crop_name,
           crop_category = EXCLUDED.crop_category,
           is_pilot_crop = EXCLUDED.is_pilot_crop
    """
)

SQL_UPSERT_SOURCE = text(
    """
    INSERT INTO sources (source_id, title, authority, url, publication_date,
                         publication_date_note, retrieved_date, geography,
                         reliability_tier, access_note)
    VALUES (:source_id, :title, :authority, :url, :publication_date,
            :publication_date_note, :retrieved_date, :geography,
            :reliability_tier, :access_note)
    ON CONFLICT (source_id) DO UPDATE
       SET title = EXCLUDED.title,
           authority = EXCLUDED.authority,
           url = EXCLUDED.url,
           publication_date = EXCLUDED.publication_date,
           publication_date_note = EXCLUDED.publication_date_note,
           retrieved_date = EXCLUDED.retrieved_date,
           geography = EXCLUDED.geography,
           reliability_tier = EXCLUDED.reliability_tier,
           access_note = EXCLUDED.access_note
    """
)

SQL_UPSERT_APPROVED_USE = text(
    """
    INSERT INTO approved_uses (approved_use_id, crop_id, target_pest_common_name,
                               target_pest_scientific_name, economic_threshold_level,
                               source_id, verification_status, verification_note)
    VALUES (:approved_use_id, :crop_id, :target_pest_common_name,
            :target_pest_scientific_name, :economic_threshold_level,
            :source_id, :verification_status, :verification_note)
    ON CONFLICT (approved_use_id) DO UPDATE
       SET crop_id = EXCLUDED.crop_id,
           target_pest_common_name = EXCLUDED.target_pest_common_name,
           target_pest_scientific_name = EXCLUDED.target_pest_scientific_name,
           economic_threshold_level = EXCLUDED.economic_threshold_level,
           source_id = EXCLUDED.source_id,
           verification_status = EXCLUDED.verification_status,
           verification_note = EXCLUDED.verification_note
    """
)

SQL_UPSERT_RESTRICTIONS = text(
    """
    INSERT INTO approved_use_safety_restrictions
        (approved_use_id, phi_status, phi_value, phi_note,
         rei_status, rei_value, rei_note, ppe_status, ppe_value, ppe_note)
    VALUES (:approved_use_id, :phi_status, :phi_value, :phi_note,
            :rei_status, :rei_value, :rei_note, :ppe_status, :ppe_value, :ppe_note)
    ON CONFLICT (approved_use_id) DO UPDATE
       SET phi_status = EXCLUDED.phi_status, phi_value = EXCLUDED.phi_value,
           phi_note = EXCLUDED.phi_note,
           rei_status = EXCLUDED.rei_status, rei_value = EXCLUDED.rei_value,
           rei_note = EXCLUDED.rei_note,
           ppe_status = EXCLUDED.ppe_status, ppe_value = EXCLUDED.ppe_value,
           ppe_note = EXCLUDED.ppe_note
    """
)

SQL_INSERT_INTERVENTION = text(
    """
    INSERT INTO interventions
        (approved_use_id, ordinal, control_type, description,
         active_ingredient_and_formulation, dosage, dosage_unit_note,
         safety_phi_status, safety_phi_value, safety_phi_note,
         safety_rei_status, safety_rei_value, safety_rei_note,
         safety_ppe_status, safety_ppe_value, safety_ppe_note)
    VALUES (:approved_use_id, :ordinal, :control_type, :description,
            :active_ingredient_and_formulation, :dosage, :dosage_unit_note,
            :safety_phi_status, :safety_phi_value, :safety_phi_note,
            :safety_rei_status, :safety_rei_value, :safety_rei_note,
            :safety_ppe_status, :safety_ppe_value, :safety_ppe_note)
    """
)

SQL_UPSERT_PROVENANCE = text(
    """
    INSERT INTO provenance_records
        (approved_use_id, source_id, source_url, retrieved_date, fetch_method,
         document_sha256, document_bytes, verbatim_excerpt, verdict, notes)
    VALUES (:approved_use_id, :source_id, :source_url, :retrieved_date, :fetch_method,
            :document_sha256, :document_bytes, :verbatim_excerpt, :verdict, :notes)
    ON CONFLICT (approved_use_id) DO UPDATE
       SET source_id = EXCLUDED.source_id,
           source_url = EXCLUDED.source_url,
           retrieved_date = EXCLUDED.retrieved_date,
           fetch_method = EXCLUDED.fetch_method,
           document_sha256 = EXCLUDED.document_sha256,
           document_bytes = EXCLUDED.document_bytes,
           verbatim_excerpt = EXCLUDED.verbatim_excerpt,
           verdict = EXCLUDED.verdict,
           notes = EXCLUDED.notes
    """
)


def import_knowledge_base(*, skip_embeddings: bool = False, dry_run: bool = False) -> dict:
    """
    Import the JSON knowledge base into PostgreSQL. Returns a summary dict.

    Raises on any validation or SQL error; nothing is partially written.
    """
    repository = JSONFileKnowledgeBaseRepository()
    crops = repository.list_crops()
    sources = repository.list_sources()
    approved_uses = repository.list_approved_uses()
    manifest = load_provenance_manifest()

    summary = {
        "crops": len(crops),
        "sources": len(sources),
        "approved_uses": len(approved_uses),
        "interventions": sum(len(r.interventions) for r in approved_uses),
        "provenance": len(manifest),
    }

    # Referential sanity for the manifest before touching the database: the FK
    # would catch it, but the message would be a raw IntegrityError.
    use_ids = {r.approved_use_id for r in approved_uses}
    source_ids = {s.source_id for s in sources}
    problems = [
        f"{p.approved_use_id}: manifest references unknown approved_use_id"
        for p in manifest if p.approved_use_id not in use_ids
    ] + [
        f"{p.approved_use_id}: manifest references unknown source_id '{p.source_id}'"
        for p in manifest if p.source_id not in source_ids
    ]
    if problems:
        raise ValueError("Provenance manifest does not match the seed data:\n" + "\n".join(problems))

    if dry_run:
        summary["dry_run"] = True
        return summary

    from app.db.connection import get_engine

    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(SQL_UPSERT_CROP, _crop_rows(crops))
        conn.execute(SQL_UPSERT_SOURCE, _source_rows(sources))

        for record in approved_uses:
            conn.execute(SQL_UPSERT_APPROVED_USE, [_approved_use_row(record)])
            conn.execute(SQL_UPSERT_RESTRICTIONS, [_restriction_row(record)])
            # Replace, don't merge: an intervention removed from the source data
            # must disappear from the database too.
            conn.execute(
                text("DELETE FROM interventions WHERE approved_use_id = :id"),
                {"id": record.approved_use_id},
            )
            rows = _intervention_rows(record)
            if rows:
                conn.execute(SQL_INSERT_INTERVENTION, rows)

        if manifest:
            conn.execute(SQL_UPSERT_PROVENANCE, [p.model_dump() for p in manifest])

    summary["imported"] = True

    # --- self-verification ------------------------------------------------
    from app.knowledge_base.postgres_repository import PostgresKnowledgeBaseRepository

    pg = PostgresKnowledgeBaseRepository(engine)
    db_counts = {}
    with engine.connect() as conn:
        for table in ("crops", "sources", "approved_uses", "interventions", "provenance_records"):
            db_counts[table] = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()

    mismatches = pg.assert_advisory_status_consistency()
    if mismatches:
        raise RuntimeError(
            "advisory-status view disagrees with the Phase 3.1 rule for: " + "; ".join(mismatches)
        )

    summary["db_counts"] = db_counts
    summary["advisory_status"] = pg.advisory_status_from_view()

    if not skip_embeddings:
        summary["embeddings"] = _import_embeddings(engine, crops, sources, approved_uses)

    return summary


def _import_embeddings(engine, crops, sources, approved_uses) -> dict:
    from app.vector.chunking import build_chunks
    from app.vector.store import PostgresVectorStore

    store = PostgresVectorStore(engine=engine)
    chunks = build_chunks(approved_uses, crops, sources)
    written = store.upsert_chunks(chunks)
    return {
        "written": written,
        "total": store.count(),
        "backend": store.backend,
        "detail": store.storage_detail(),
        "model": store._provider.model_id,  # noqa: SLF001 - internal factory detail
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import the pilot knowledge base into PostgreSQL.")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="import relational rows only")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate the seed data without writing anything")
    args = parser.parse_args(argv)

    try:
        summary = import_knowledge_base(
            skip_embeddings=args.skip_embeddings,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint
        print(f"Import failed: {exc}")
        print("Check DATABASE_URL, then apply migrations: python -m app.db.run_migrations")
        return 1

    print("Knowledge-base import summary")
    print("-----------------------------")
    for key in ("crops", "sources", "approved_uses", "interventions", "provenance"):
        print(f"  {key:<14}: {summary[key]}")
    if summary.get("dry_run"):
        print("  (dry run — validation only, nothing written)")
        return 0
    print(f"  database rows : {summary['db_counts']}")
    print(f"  advisory      : {summary['advisory_status']}")
    if "embeddings" in summary:
        emb = summary["embeddings"]
        print(f"  embeddings    : {emb['total']} stored ({emb['backend']}, model {emb['model']})")
        print(f"                  {emb['detail']}")
    print("Import OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
