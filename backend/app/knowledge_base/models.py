"""
Module C — Knowledge Representation: data models.

These models mirror the entities defined in the approved architecture blueprint
(01_Blueprint/PROJECT_ARCHITECTURE_BLUEPRINT.md, Section 9 — Database and
Knowledge-Base Schema): sources, crops, approved_use, safety_restriction.

IMPORTANT (Phase 3 scope / anti-fabrication design):
- These are plain Pydantic models, NOT SQLAlchemy ORM models bound to a live
  database. The knowledge-base layer must work before PostgreSQL is reachable
  (DEC-008 known gap) and must not block on it. A PostgreSQL-backed repository
  implementing the same `KnowledgeBaseRepository` interface (see repository.py)
  can be added later without changing this schema.
- `SafetyField.status` is NOT optional and has no default. Every PHI/REI/PPE
  value must be explicitly declared as either "PUBLISHED" (with a value) or
  "NOT_PUBLISHED_IN_SOURCE". This makes it structurally impossible to silently
  omit a safety field — the loader will reject a record that leaves it out,
  rather than defaulting it to null and letting it look verified.
- `verification_status` is restricted to a closed set of honest values. None of
  them is "approved" or "registered" — this project has not cross-checked any
  record against the live CIB&RC product-registration database, and the schema
  must never imply that it has. See the module-level distinction below between
  *source verification* (we transcribed this text correctly from a named,
  fetchable page) and *regulatory approval* (CIB&RC has certified this exact
  product/crop/dose combination) — this schema only ever claims the former.

PHASE 3.1 ADDITIONS (DEC-010, safety-and-provenance audit):
- `SafetyField._value_required_if_published` from Phase 3 was a dead/no-op
  field_validator (it returned the value unchanged and asserted nothing). The
  real "PUBLISHED requires a value / NOT_PUBLISHED_IN_SOURCE requires a note"
  rule has only ever lived in `SafetyRestrictions.model_post_init`. The no-op
  validator has been removed rather than left as misleading documentation.
- `ApprovedUse.interventions` now requires at least one entry (`min_length=1`):
  Phase 3's schema silently accepted an empty intervention list.
- `Source` now enforces at schema level (not just by a data-level test) that a
  missing `publication_date` must carry a `publication_date_note`.
- `Intervention.safety_restrictions` (optional) lets a future per-product PHI/
  REI/PPE value be recorded against a *specific* chemical intervention — PHI/
  REI legally attach to a product+label, not to an entire pest-management
  record that may list several interchangeable products. The record-level
  `ApprovedUse.safety_restrictions` is kept unchanged for backward
  compatibility; nothing auto-copies between the two levels, and the Phase 3
  pilot dataset deliberately leaves every per-intervention field absent (no
  per-product PHI/REI/PPE has been found in any source yet — see DEC-010).
- `ApprovedUse.advisory_status` (computed, response-only) implements Decision 1
  from DEC-010: a record may be rendered as an *actionable* recommendation only
  when every chemical intervention's safety profile (PHI+REI+PPE, taken from
  the intervention level if present, else the record level) is fully
  PUBLISHED. Any gap anywhere keeps the whole record `EDUCATIONAL_ONLY` — still
  retrievable for RAG/education, never presented as a safe, actionable dose.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

VerificationStatus = Literal[
    # Dosage/management data is a direct, traceable quotation from a named
    # authoritative Indian source (state agricultural university extension
    # portal, or a national ICAR/NIPHM-DPPQS IPM package). It has NOT been
    # independently cross-checked against the live CIB&RC product
    # registration database, so it must never be presented as a confirmed
    # current product registration/approval.
    "VERIFIED_SOURCE_RECOMMENDATION",
    # Anything that does not yet meet the bar above (e.g., drafted but not
    # traced to a fetchable source). No such records should ship in the seed
    # dataset, but the type exists so the loader/tests can actively check
    # that none exist, rather than assuming it.
    "UNVERIFIED_DRAFT",
]

ReliabilityTier = Literal[
    "national_regulator_ipm_package",   # NIPHM / DPPQS (parent directorate of CIB&RC)
    "state_agricultural_university",    # e.g., TNAU
]


class Source(BaseModel):
    """Mirrors blueprint `sources` table."""

    source_id: str
    title: str
    authority: str
    url: str
    publication_date: Optional[str] = Field(
        default=None,
        description="ISO date or year-month if the source explicitly states one. "
        "Null (with publication_date_note explaining why) if the source page "
        "does not publish a date — never guessed.",
    )
    publication_date_note: Optional[str] = None
    retrieved_date: str = Field(description="Date this office actually fetched the page (ISO date).")
    geography: str
    reliability_tier: ReliabilityTier
    access_note: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _url_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://") and not v.startswith("http://"):
            raise ValueError(f"source url must be an http(s) URL, got: {v}")
        return v

    @model_validator(mode="after")
    def _publication_date_gap_must_be_explained(self) -> "Source":
        """
        Phase 3.1 (F8): Phase 3 only checked this at the dataset/test level
        (test_sources_without_explicit_publication_date_carry_a_note). Moving
        the rule into the schema means a future bad source record fails at
        construction time, the same way a bad safety field already does.
        """
        if self.publication_date is None and not self.publication_date_note:
            raise ValueError(
                "source has no publication_date and no publication_date_note explaining "
                "the gap — a missing date must never be silent"
            )
        return self


class Crop(BaseModel):
    """Mirrors blueprint `crops` table."""

    crop_id: str
    crop_name: str
    crop_category: str
    is_pilot_crop: bool = True


class SafetyField(BaseModel):
    """
    One safety-critical field (PHI, REI, or PPE). `status` is mandatory with
    no default so a record author cannot accidentally leave a safety field
    unaddressed — see module docstring.
    """

    status: Literal["PUBLISHED", "NOT_PUBLISHED_IN_SOURCE"]
    value: Optional[str] = None
    note: Optional[str] = None


class SafetyRestrictions(BaseModel):
    """Mirrors blueprint `safety_restriction` rows for one approved_use entry."""

    phi: SafetyField
    rei: SafetyField
    ppe: SafetyField

    def model_post_init(self, __context) -> None:  # pydantic v2 hook
        for field_name in ("phi", "rei", "ppe"):
            field: SafetyField = getattr(self, field_name)
            if field.status == "PUBLISHED" and not field.value:
                raise ValueError(
                    f"safety field '{field_name}' is marked PUBLISHED but has no value"
                )
            if field.status == "NOT_PUBLISHED_IN_SOURCE" and not field.note:
                raise ValueError(
                    f"safety field '{field_name}' is NOT_PUBLISHED_IN_SOURCE and must carry "
                    f"an explicit 'note' explaining the gap (never leave it silent)"
                )


class Intervention(BaseModel):
    """
    One recommended measure for a pest/crop pair. `control_type` keeps
    chemical options visually distinct from cultural/biological ones (the
    source documents mix all three; we must not collapse that distinction).

    PHASE 3.1 (DEC-010, F2): `safety_restrictions` is new and OPTIONAL. PHI/
    REI/PPE legally attach to a specific registered product+label, not to an
    entire pest-management record that may list several interchangeable
    chemical options with different restrictions. This field lets a future
    source that publishes per-product safety data be recorded precisely,
    without forcing every record to invent one. It is intentionally left
    unset (None) for the whole Phase 3 pilot dataset — no source fetched so
    far publishes a per-product PHI/REI/PPE value, and nothing here is
    auto-copied from the record-level `ApprovedUse.safety_restrictions` to
    avoid implying a per-product value was actually sourced when it was not.
    """

    control_type: Literal["chemical", "biological", "cultural", "mechanical"]
    description: str = Field(description="Verbatim-as-practical quote/paraphrase of the measure from the source.")
    active_ingredient_and_formulation: Optional[str] = None
    dosage: Optional[str] = None
    dosage_unit_note: Optional[str] = Field(
        default=None,
        description="Flags any apparent unit inconsistency observed in the original source text "
        "(e.g., a liquid formulation dosed in grams) instead of silently 'correcting' it.",
    )
    safety_restrictions: Optional["SafetyRestrictions"] = Field(
        default=None,
        description="Per-product PHI/REI/PPE, only when a source publishes it for THIS specific "
        "intervention. None (not an empty/placeholder object) means no per-product safety data "
        "has been sourced for this intervention — the record-level safety_restrictions still "
        "applies as the record's overall (not product-specific) safety disclosure.",
    )


class ApprovedUse(BaseModel):
    """
    Mirrors blueprint `approved_use` table, adapted for pest-management
    recommendation sources (TNAU / NIPHM-DPPQS) rather than a single-product
    CIB&RC label lookup. See module docstring and `verification_status`.
    """

    approved_use_id: str
    crop_id: str
    target_pest_common_name: str
    target_pest_scientific_name: Optional[str] = None
    economic_threshold_level: Optional[str] = None
    interventions: list[Intervention] = Field(min_length=1)
    safety_restrictions: SafetyRestrictions
    source_id: str
    verification_status: VerificationStatus
    verification_note: str = Field(
        description="Mandatory, human-readable honesty statement about what has and has not "
        "been verified for this record (e.g., not cross-checked against live CIB&RC registry)."
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def advisory_status(self) -> Literal["ACTIONABLE_WITH_EVIDENCE", "EDUCATIONAL_ONLY"]:
        """
        PHASE 3.1 (DEC-010, Decision 1): the rule-engine veto described in the
        blueprint (§12 RequireSafetyFields) does not exist yet (Phase 6), but
        this computed field implements its gating *intent* today so that no
        consumer — API, frontend, or a future RAG/rule module — can present an
        incomplete-safety record as an actionable dose. A record is
        'ACTIONABLE_WITH_EVIDENCE' only when every chemical intervention has a
        fully PUBLISHED PHI+REI+PPE profile (checked at the intervention level
        if it carries its own safety_restrictions, otherwise falling back to
        the record-level safety_restrictions). Any gap anywhere — including
        today's reality that 0 of 9 pilot records have ANY published safety
        field — keeps the whole record 'EDUCATIONAL_ONLY': still retrievable
        for RAG/education, never rendered as a safe, actionable recommendation.
        Non-chemical interventions (biological/cultural/mechanical) do not
        carry PHI/REI/PPE in agronomic practice and are not evaluated here.
        """
        chemical_interventions = [i for i in self.interventions if i.control_type == "chemical"]
        if not chemical_interventions:
            # No chemical option at all (e.g. a purely cultural/mechanical
            # record) -> there is no pesticide-safety profile to gate on, but
            # this project's scope is pesticide advisory, so such a record is
            # still treated as educational-only rather than actionable.
            return "EDUCATIONAL_ONLY"
        for interv in chemical_interventions:
            restrictions = interv.safety_restrictions or self.safety_restrictions
            for field_name in ("phi", "rei", "ppe"):
                if getattr(restrictions, field_name).status != "PUBLISHED":
                    return "EDUCATIONAL_ONLY"
        return "ACTIONABLE_WITH_EVIDENCE"
