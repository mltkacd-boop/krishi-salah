"""
Module D support — deterministic chunk construction (Phase 5, DEC-012).

Chunks are derived from the validated knowledge-base records, never hand-written.
That matters for provenance: a retrieved chunk can always be traced back to an
`approved_use_id` and therefore to the source, the provenance manifest entry and
the advisory-status gate.

Three chunk types, matching the `embeddings.chunk_type` CHECK constraint:

  approved_use   one per record — crop, pest, threshold
  intervention   one per recommended measure — includes the source's dosage text
  source         one per source — title, authority, geography

SAFETY NOTE: an `intervention` chunk may contain a dosage string. Storing it is
required for retrieval, but a chunk is *not* a recommendation. Every search
result carries the record's derived `advisory_status` so a consumer cannot render
a dosage without also seeing whether the record is EDUCATIONAL_ONLY. The gate is
applied by the consumer (Phase 6/7 rule engine), and the value it reads comes
from the database view, not from this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.knowledge_base.models import ApprovedUse, Crop, Source


@dataclass(frozen=True)
class ChunkInput:
    chunk_type: str
    chunk_ref: str
    approved_use_id: str | None
    content: str


def _clean(parts: list[str | None]) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def _sentence(value: str | None) -> str | None:
    """
    Format a source value as one sentence without doubling punctuation.

    Source values frequently already end in '.', ')', or a full stop after a
    parenthetical. Appending a second '.' produced strings like
    "... (as stated on source page).." during verification. This only fixes
    presentation; the text content itself is never reworded.
    """
    if not value or not value.strip():
        return None
    cleaned = value.strip()
    return cleaned if cleaned.endswith((".", "!", "?", ")", ":")) else cleaned + "."


def chunk_approved_use(record: ApprovedUse, crop: Crop | None) -> ChunkInput:
    crop_name = crop.crop_name if crop else record.crop_id
    content = _clean([
        f"Crop: {crop_name}.",
        f"Pest: {record.target_pest_common_name}.",
        f"Scientific name: {_sentence(record.target_pest_scientific_name)}"
        if record.target_pest_scientific_name else None,
        f"Economic threshold: {_sentence(record.economic_threshold_level)}"
        if record.economic_threshold_level else None,
    ])
    return ChunkInput("approved_use", record.approved_use_id, record.approved_use_id, content)


def chunk_interventions(record: ApprovedUse, crop: Crop | None) -> list[ChunkInput]:
    crop_name = crop.crop_name if crop else record.crop_id
    chunks: list[ChunkInput] = []
    for index, intervention in enumerate(record.interventions, start=1):
        content = _clean([
            f"Crop: {crop_name}.",
            f"Pest: {record.target_pest_common_name}.",
            f"Measure type: {intervention.control_type}.",
            f"Measure: {intervention.description}",
            f"Active ingredient and formulation: {_sentence(intervention.active_ingredient_and_formulation)}"
            if intervention.active_ingredient_and_formulation else None,
            f"Dosage: {_sentence(intervention.dosage)}" if intervention.dosage else None,
        ])
        chunks.append(ChunkInput(
            "intervention",
            f"{record.approved_use_id}#{index}",
            record.approved_use_id,
            content,
        ))
    return chunks


def chunk_source(source: Source) -> ChunkInput:
    content = _clean([
        f"Source: {source.title}.",
        f"Authority: {source.authority}.",
        f"Geography: {source.geography}.",
        f"Reliability tier: {source.reliability_tier}.",
    ])
    return ChunkInput("source", source.source_id, None, content)


def build_chunks(
    approved_uses: list[ApprovedUse],
    crops: list[Crop],
    sources: list[Source],
) -> list[ChunkInput]:
    """All chunks for the knowledge base, in a stable order (ids are deterministic)."""
    crop_by_id = {c.crop_id: c for c in crops}
    chunks: list[ChunkInput] = []
    for record in approved_uses:
        crop = crop_by_id.get(record.crop_id)
        chunks.append(chunk_approved_use(record, crop))
        chunks.extend(chunk_interventions(record, crop))
    for source in sources:
        chunks.append(chunk_source(source))
    return chunks
