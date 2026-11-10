"""
Phase 6 — evidence selection, crop/pest conditioning and sufficiency gating.

TWO MEASURED FINDINGS DRIVE THIS MODULE
---------------------------------------
1. **Similarity cannot decide whether to answer.** With the default lexical
   embedder, the in-scope Hindi query "धान का तना छेदक" scores 0.111 against
   relevant chunks, while the out-of-scope "what is the mandi price of rice
   today" scores 0.311. The wrong question scores higher. So similarity is used
   for ranking and confidence only; the answer/no-answer decision comes from the
   Phase 4 classifier plus crop agreement.

2. **Crop agreement alone does not pick the right record.** Within one crop,
   several records tie on crop boost, and raw similarity picked "Spotted
   bollworm / Spiny bollworm" for a pink-bollworm query during development. So
   records are additionally scored on *pest-name alignment*, weighted by how rare
   each matching token is ("pink" distinguishes; "borer" does not).

WHAT HAPPENS WHEN THE PEST CANNOT BE MATCHED
--------------------------------------------
* Latin-script query naming a pest that no record covers (whitefly, bacterial
  blight): refused as insufficient evidence. Answering with a neighbouring pest
  would be a wrong answer dressed in real data.
* Devanagari query: the lexical embedder has no cross-lingual ability, so a Hindi
  pest name can never align with the English record names. Rather than guess, the
  pipeline answers at *crop level*: it lists the records that exist for that crop,
  labelled as such, with citations. Honest, still useful, and it never claims a
  pest match it does not have.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from app.classification.schemas import ClassifyResponse
from app.knowledge_base.models import ApprovedUse, Source
from app.vector.store import RetrievedChunk, VectorStore

# A chunk must be faintly similar to be considered at all. Deliberately low:
# Devanagari queries measure 0.086-0.111 against relevant chunks, so a
# "confident-looking" floor such as 0.30 would silently drop every Hindi answer.
MIN_CHUNK_SIMILARITY = 0.05

CROP_MATCH_BOOST = 0.25
CROP_MISMATCH_PENALTY = 0.20
PEST_ALIGNMENT_WEIGHT = 0.36
PEST_ALIGNMENT_CAP = 0.45

# An `out_of_scope` verdict is only acted on when the task head is reasonably
# sure. Below this, the query keeps its crop context and retrieval proceeds:
# refusing a genuine Hindi pest question because the task head was unsure is a
# false negative.
OUT_OF_SCOPE_CONFIDENCE_FLOOR = 0.55

SIM_FLOOR_FOR_CONFIDENCE = 0.05
SIM_CEIL_FOR_CONFIDENCE = 0.40

PILOT_CROPS = frozenset({"rice", "wheat", "maize", "cotton", "tomato"})
SAFETY_VALUE_TOPICS = {"phi", "rei", "ppe"}

# Words that carry no pest identity. Kept small and explicit; anything not here
# and not in the pest vocabulary is treated as a possible pest term.
STOPWORDS = frozenset({
    "about", "after", "before", "best", "control", "cotton", "crop", "crops",
    "disease", "diseases", "dose", "dosage", "during", "early", "from", "harvest",
    "help", "insect", "insects", "insecticide", "insecticides", "into", "maize",
    "manage", "management", "need", "pest", "pests", "pesticide", "plant", "please",
    "problem", "rice", "safe", "safety", "should", "spray", "spraying", "treat",
    "treatment", "use", "wheat", "what", "when", "which", "with", "long", "many",
    "days", "day", "wait", "waiting", "period", "interval", "time", "much",
    "कपास", "धान", "गेहूं", "गेहूँ", "टमाटर", "मक्का", "कीट", "फसल",
    "कीटनाशक", "उपाय", "छिड़काव", "रोग", "सुरक्षा", "क्या", "कैसे", "कब", "और", "में",
})

_WORD_RE = re.compile(r"[A-Za-z\u0900-\u097F]+", re.UNICODE)
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


@dataclass(frozen=True)
class RankedChunk:
    chunk: RetrievedChunk
    adjusted_score: float
    crop_id: Optional[str]
    crop_matched: bool
    pest_score: float = 0.0
    pest_aligned: bool = False


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text or "")]


def is_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text or ""))


def pest_vocabulary(records: dict[str, ApprovedUse]) -> dict[str, int]:
    """
    Document frequency of each *discriminative* token across pest names.

    Crop words are excluded even when they appear in a pest name ("Rice Leaf
    Folder"): including them made "bacterial blight in rice" align with the leaf
    folder record purely on the word "rice", and the pipeline answered a disease
    question with an insect record. Only tokens that identify a pest belong here.
    """
    df: dict[str, int] = {}
    for record in records.values():
        for token in set(tokenize(record.target_pest_common_name)):
            if token in STOPWORDS:
                continue
            df[token] = df.get(token, 0) + 1
    return df


def pest_alignment(query_tokens: Sequence[str], pest_name: str, df: dict[str, int]) -> float:
    """
    Rare-token weighted overlap between the query and a pest name.

    "pink bollworm" scores 1.25 against "Pink bollworm" (pink is unique, bollworm
    is shared by four records) and 0.25 against "Spotted bollworm / Spiny
    bollworm" — which is what makes the correct record rank first.
    """
    name_tokens = set(tokenize(pest_name))
    score = 0.0
    for token in set(query_tokens):
        if token in STOPWORDS:
            # Crop and generic words never establish a pest match. Without this,
            # "bacterial blight in rice" aligned to "Rice Leaf Folder" on the word
            # "rice" and answered a disease question with an insect record.
            continue
        if token in name_tokens:
            score += 1.0 / max(1, df.get(token, 1))
    return score


def unknown_pest_terms(
    query_tokens: Sequence[str], records: dict[str, ApprovedUse], df: dict[str, int]
) -> list[str]:
    """
    Query words that look like a pest or disease name but match no record.

    Only meaningful for Latin script: a Devanagari token can never match an
    English record name, so it would always be reported as "unknown" and would
    turn every Hindi query into a refusal.
    """
    known = set(df)
    candidates: list[str] = []
    for token in query_tokens:
        if len(token) < 4 or token in STOPWORDS or token in known:
            continue
        if is_devanagari(token):
            continue
        if any(token in known_token or known_token in token for known_token in known):
            continue
        candidates.append(token)
    return candidates


def _pest_scores(
    query_tokens: Sequence[str], records: dict[str, ApprovedUse], df: dict[str, int]
) -> dict[str, float]:
    return {
        rid: pest_alignment(query_tokens, rec.target_pest_common_name, df)
        for rid, rec in records.items()
    }


def retrieve_and_rank(
    query: str,
    *,
    store: VectorStore,
    records: dict[str, ApprovedUse],
    crop_label: Optional[str],
    sources: Optional[dict[str, Source]] = None,
    limit: int = 20,
) -> list[RankedChunk]:
    """
    Retrieve broadly, then re-rank by crop agreement and pest-name alignment.

    Retrieval is not filtered by crop at the SQL level on purpose: the classifier
    can be wrong, and pre-filtering would convert one classification error into an
    empty result with no diagnostic trail.

    It *is* filtered by attributability when `sources` is supplied: a chunk whose
    record is not in the knowledge base, or whose record points at a source that
    does not exist, is discarded. Such a chunk could only be answered from without
    a citation, which is exactly the failure mode this pipeline exists to prevent.
    """
    query_tokens = tokenize(query)
    df = pest_vocabulary(records)
    pest_scores = _pest_scores(query_tokens, records, df)

    raw = store.search(query, limit=limit)
    ranked: list[RankedChunk] = []
    for chunk in raw:
        if chunk.score < MIN_CHUNK_SIMILARITY:
            continue
        record = records.get(chunk.approved_use_id or "")
        if record is None:
            continue  # orphan chunk: no record to attribute it to
        if sources is not None and record.source_id not in sources:
            continue  # record's source is missing: the claim is un-citable
        crop_id = record.crop_id
        matched = bool(crop_label in PILOT_CROPS and crop_id == crop_label)
        pest_score = pest_scores.get(chunk.approved_use_id or "", 0.0)

        adjusted = chunk.score
        if crop_label in PILOT_CROPS and crop_id is not None:
            adjusted += CROP_MATCH_BOOST if matched else -CROP_MISMATCH_PENALTY
        adjusted += min(PEST_ALIGNMENT_CAP, PEST_ALIGNMENT_WEIGHT * pest_score)

        ranked.append(RankedChunk(
            chunk=chunk,
            adjusted_score=adjusted,
            crop_id=crop_id,
            crop_matched=matched,
            pest_score=pest_score,
            pest_aligned=pest_score > 0,
        ))

    ranked.sort(key=lambda r: (-r.adjusted_score, -r.chunk.score, r.chunk.chunk_ref))
    return ranked


def select_record_evidence(
    ranked: Sequence[RankedChunk],
    *,
    record_id: str,
    max_items: int,
) -> list[RankedChunk]:
    """
    Evidence for one record: its own chunks only.

    Deliberately excludes chunks from other records. Mixing records produced an
    answer that merged leaf-folder and stem-borer measures during development,
    which reads as a single recommendation for neither pest.
    """
    own = [r for r in ranked if r.chunk.approved_use_id == record_id]
    own.sort(key=lambda r: (0 if r.chunk.chunk_type == "approved_use" else 1, -r.adjusted_score))
    return own[:max_items]


def select_crop_evidence(
    ranked: Sequence[RankedChunk],
    *,
    crop_id: str,
    max_records: int,
) -> list[RankedChunk]:
    """Best chunk per record for a crop — used for crop-level answers."""
    best: dict[str, RankedChunk] = {}
    for item in ranked:
        if item.crop_id != crop_id or not item.chunk.approved_use_id:
            continue
        current = best.get(item.chunk.approved_use_id)
        if current is None or item.adjusted_score > current.adjusted_score:
            best[item.chunk.approved_use_id] = item
    ordered = sorted(best.values(), key=lambda r: -r.adjusted_score)
    return ordered[:max_records]


def crop_matched(ranked: Sequence[RankedChunk]) -> list[RankedChunk]:
    return [r for r in ranked if r.crop_matched]


def safety_value_available(record: Optional[ApprovedUse], topic: str) -> tuple[bool, str]:
    """
    A PHI/REI/PPE question is answerable only from a PUBLISHED value.

    No record in the current knowledge base publishes one, so this returns False
    and the caller emits an explicit "not published in source" escalation instead
    of quoting a dose or a neighbouring value as if it answered the question.
    """
    if record is None or topic not in SAFETY_VALUE_TOPICS:
        return False, "safety_value_not_published"
    field = getattr(record.safety_restrictions, topic)
    if field.status != "PUBLISHED" or not field.value:
        return False, "safety_value_not_published"
    return True, "ok"


def retrieval_confidence(ranked: Sequence[RankedChunk]) -> float:
    """Raw similarity of the best chunk, mapped to [0,1]. Re-ranking is excluded."""
    if not ranked:
        return 0.0
    best = max(r.chunk.score for r in ranked)
    span = SIM_CEIL_FOR_CONFIDENCE - SIM_FLOOR_FOR_CONFIDENCE
    return max(0.0, min(1.0, (best - SIM_FLOOR_FOR_CONFIDENCE) / span))


def combine_confidence(retrieval: float, classification_confidence: float) -> float:
    """
    Retrieval-heavy blend, capped below 1.0.

    With a lexical embedder and nine records, an absolute certainty claim would be
    false precision.
    """
    blended = 0.6 * retrieval + 0.4 * max(0.0, min(1.0, classification_confidence))
    return round(min(0.95, blended), 3)


def confidence_label(value: float) -> Literal["low", "medium", "high"]:
    if value < 0.45:
        return "low"
    if value < 0.70:
        return "medium"
    return "high"


def provenance_index(provenance_rows: Sequence[dict]) -> dict[str, str]:
    return {
        row["approved_use_id"]: row["document_sha256"][:16]
        for row in provenance_rows
        if row.get("document_sha256")
    }


def select_crop_records(
    records: dict[str, ApprovedUse], *, crop_id: str, max_records: int
) -> list[str]:
    """
    Record ids for a crop, without consulting the retriever.

    Needed for the crop-level answer: a Devanagari query about cotton scored
    highest against *maize* and *tomato* chunks (0.086 vs nothing relevant), so
    retrieval cannot be the source of "which records belong to this crop". The
    classifier's crop label plus the knowledge base can.
    """
    selected = [r for r in records.values() if r.crop_id == crop_id]
    selected.sort(key=lambda r: r.target_pest_common_name.lower())
    return [r.approved_use_id for r in selected][:max_records]


def build_citation_map(
    record_objs: Sequence[ApprovedUse],
    sources: dict[str, Source],
    provenance: dict[str, str],
    selected: Sequence[RankedChunk],
) -> list[dict]:
    """
    Group the cited records under their sources so every claim is attributable.

    Built from the records actually used, not from whatever the retriever
    returned, so a crop-level answer still cites its sources when retrieval found
    nothing for that crop. A record whose source is missing is dropped rather than
    cited with a guessed title.
    """
    refs_by_record: dict[str, list[str]] = {}
    for item in selected:
        rid = item.chunk.approved_use_id
        if rid:
            refs_by_record.setdefault(rid, []).append(item.chunk.chunk_ref)

    by_source: dict[str, dict] = {}
    for record in record_objs:
        source = sources.get(record.source_id)
        if source is None:
            continue
        entry = by_source.setdefault(source.source_id, {
            "source": source,
            "verification_status": record.verification_status,
            "provenance_sha256": provenance.get(record.approved_use_id),
            "chunk_refs": [],
            "record_ids": [],
        })
        # If any record sharing this source is only a draft, the citation says so.
        if record.verification_status == "UNVERIFIED_DRAFT":
            entry["verification_status"] = "UNVERIFIED_DRAFT"
        if entry["provenance_sha256"] is None:
            entry["provenance_sha256"] = provenance.get(record.approved_use_id)
        entry["chunk_refs"].extend(refs_by_record.get(record.approved_use_id, []))
        entry["record_ids"].append(record.approved_use_id)
    return [by_source[key] for key in sorted(by_source)]


def decide(
    *,
    ranked: Sequence[RankedChunk],
    classification: ClassifyResponse,
    records: dict[str, ApprovedUse],
    query: str,
) -> tuple[str, str, Optional[str], str]:
    """
    Decide the outcome before any text is generated.

    Returns (outcome, detail_code, record_id_or_None, answer_scope) where
    answer_scope is "record" or "crop". Deciding first is what guarantees no
    confident paragraph can be composed for a question that should be declined.
    """
    crop_label = classification.crop.label

    if classification.unsupported:
        return "unsupported_crop", "classifier_unsupported_crop", None, "record"

    if classification.out_of_scope:
        if classification.task.confidence >= OUT_OF_SCOPE_CONFIDENCE_FLOOR:
            return "out_of_scope", "classifier_out_of_scope", None, "record"
        # Low-confidence out_of_scope with a recognised pilot crop: keep going.
        if crop_label not in PILOT_CROPS:
            return "needs_clarification", "low_confidence_out_of_scope", None, "record"

    if classification.safety_topic.label == "regulatory_approval":
        # Never cross-checked against the CIB&RC registry; retrieval cannot fix that.
        return "no_regulatory_verification", "regulatory_topic", None, "record"

    if crop_label not in PILOT_CROPS:
        # No crop recognised: "hello" and other non-agronomic input. Prefer the
        # classifier's own clarification request over a bare no-evidence refusal.
        if classification.requires_clarification:
            return "needs_clarification", "classifier_needs_clarification", None, "record"
        return "insufficient_evidence", "no_pilot_crop", None, "record"

    matched = crop_matched(ranked)
    aligned = [r for r in matched if r.pest_aligned and r.chunk.approved_use_id]

    # A PHI/REI/PPE question is answered from a PUBLISHED value or not at all.
    # Checked before pest alignment because the question is about a safety value,
    # not about a pest: "how long before harvest after spraying cotton" names no
    # pest at all, and must not be refused as an unmatched pest.
    if classification.safety_topic.label in SAFETY_VALUE_TOPICS:
        topic = classification.safety_topic.label
        candidate_id = (
            aligned[0].chunk.approved_use_id if aligned
            else (matched[0].chunk.approved_use_id if matched else None)
        )
        ok, code = safety_value_available(records.get(candidate_id or ""), topic)
        if not ok:
            return "safety_value_not_published", code, candidate_id, "record"
        return "answered", "safety_value_published", candidate_id, "record"

    if aligned:
        return "answered", "pest_matched", aligned[0].chunk.approved_use_id, "record"

    # Clarification is honoured only when the query does NOT already resolve to a
    # record. The Phase 4 classifier asks for clarification when the task verb is
    # missing ("wheat termite") or the safety topic is ambiguous, but a query that
    # names a crop and a pest mapping to exactly one record has nothing left to
    # ask: that record carries identification, measures and safety limits
    # together. Asking anyway would refuse the single most common query shape.
    if classification.requires_clarification:
        return "needs_clarification", "classifier_needs_clarification", None, "record"

    # No pest alignment.
    if is_devanagari(query):
        # Cross-lingual matching is not possible with this embedder. Answer at
        # crop level rather than pretend to have matched a pest name.
        return "answered", "crop_level_hindi", None, "crop"

    if not matched:
        return "insufficient_evidence", "no_crop_matched_evidence", None, "record"

    unknown = unknown_pest_terms(tokenize(query), records, pest_vocabulary(records))
    if unknown:
        return "insufficient_evidence", f"pest_not_in_knowledge_base:{unknown[0]}", None, "record"

    # A generic crop question ("cotton pest control"): present the crop's records.
    return "answered", "crop_level_generic", None, "crop"
