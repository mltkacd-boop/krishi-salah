/**
 * Response shapes returned by the Milestone 1 backend health endpoints.
 * Must stay in sync with backend/app/schemas/health.py.
 */

export interface LivenessResponse {
  status: string
  service: string
}

export interface DependencyStatus {
  connected: boolean
  message: string
}

export interface LLMStatus {
  provider: string
  available: boolean
  message: string
}

export interface ReadinessResponse {
  status: 'ready' | 'degraded'
  database: DependencyStatus
  pgvector: DependencyStatus
  llm: LLMStatus
  supported_languages: string[]
}

/**
 * Phase 3 Knowledge Base (Module C) types. Must stay in sync with
 * backend/app/knowledge_base/models.py. These mirror a deliberately
 * anti-fabrication schema: every safety field is either PUBLISHED (with a
 * value) or NOT_PUBLISHED_IN_SOURCE (with a note) - never silently absent.
 */
export interface Crop {
  crop_id: string
  crop_name: string
  crop_category: string
  is_pilot_crop: boolean
}

export interface Source {
  source_id: string
  title: string
  authority: string
  url: string
  publication_date: string | null
  publication_date_note: string | null
  retrieved_date: string
  geography: string
  reliability_tier: 'national_regulator_ipm_package' | 'state_agricultural_university'
  access_note: string | null
}

export interface SafetyField {
  status: 'PUBLISHED' | 'NOT_PUBLISHED_IN_SOURCE'
  value: string | null
  note: string | null
}

export interface SafetyRestrictions {
  phi: SafetyField
  rei: SafetyField
  ppe: SafetyField
}

export interface Intervention {
  control_type: 'chemical' | 'biological' | 'cultural' | 'mechanical'
  description: string
  active_ingredient_and_formulation: string | null
  dosage: string | null
  dosage_unit_note: string | null
  /**
   * Phase 3.1 (DEC-010): optional per-product PHI/REI/PPE. null means no
   * source has published a per-product safety value for this specific
   * intervention yet - the record-level safety_restrictions still applies
   * as the record's overall (not product-specific) safety disclosure.
   */
  safety_restrictions: SafetyRestrictions | null
}

export interface ApprovedUse {
  approved_use_id: string
  crop_id: string
  target_pest_common_name: string
  target_pest_scientific_name: string | null
  economic_threshold_level: string | null
  interventions: Intervention[]
  safety_restrictions: SafetyRestrictions
  source_id: string
  verification_status: 'VERIFIED_SOURCE_RECOMMENDATION' | 'UNVERIFIED_DRAFT'
  verification_note: string
  /**
   * Phase 3.1 (DEC-010, Decision 1): computed server-side. ACTIONABLE_WITH_EVIDENCE
   * only when every chemical intervention's PHI+REI+PPE are all PUBLISHED.
   * Any gap keeps the whole record EDUCATIONAL_ONLY - still shown for
   * learning/retrieval, never presented as a safe, actionable dose. As of
   * Phase 3.1, every pilot record is EDUCATIONAL_ONLY (0/9 have any
   * published safety field) - this is an honest current limitation, not a
   * bug in this field.
   */
  advisory_status: 'ACTIONABLE_WITH_EVIDENCE' | 'EDUCATIONAL_ONLY'
}

/**
 * Phase 4 (Module B) classification types. Must stay in sync with
 * backend/app/classification/schemas.py.
 *
 * These describe an *intent interpretation*, not agricultural advice. Every
 * response carries `safety_policy`, which states that classification approves
 * no pesticide recommendation and cannot lift the Phase 3.1 EDUCATIONAL_ONLY
 * gate - the UI must never present a classification result as a recommendation.
 */
export type TargetStatus =
  | 'confident'
  | 'ambiguous'
  | 'unsupported'
  | 'out_of_scope'
  | 'not_specified'
  | 'undetermined'

export interface AlternativeLabel {
  label: string
  confidence: number
}

export interface TargetResult {
  label: string | null
  display_label: string | null
  confidence: number
  margin: number
  status: TargetStatus
  alternatives: AlternativeLabel[]
}

export interface SafetyPolicy {
  approves_pesticide_recommendation: false
  can_override_educational_only_gate: false
  advisory_gate: string
  note: string
}

export interface ClassifyResponse {
  query: string
  detected_language: 'en' | 'hi' | 'hi-latn' | 'unknown'
  crop: TargetResult
  task: TargetResult
  safety_topic: TargetResult
  requires_clarification: boolean
  clarification_message: string | null
  unsupported: boolean
  out_of_scope: boolean
  scope_message: string | null
  model_version: string
  safety_policy: SafetyPolicy
}

/**
 * Phase 6/7 advisory contract. Mirrors backend/app/rag/schemas.py and
 * backend/app/rules/schemas.py. Every field here is served by the backend; the
 * UI never derives, upgrades or invents a decision or a safety value.
 */
export type AdvisoryOutcome =
  | 'answered'
  | 'needs_clarification'
  | 'out_of_scope'
  | 'unsupported_crop'
  | 'insufficient_evidence'
  | 'safety_value_not_published'
  | 'no_regulatory_verification'
  | 'safety_contradiction'

export type AdvisoryDecision =
  | 'ACTIONABLE_RECOMMENDATION'
  | 'EDUCATIONAL_INFORMATION'
  | 'SAFETY_REFUSAL'
  | 'REGULATORY_VERIFICATION_REQUIRED'
  | 'ESCALATION_REQUIRED'
  | 'CLARIFICATION_REQUIRED'

export type AdvisoryStatus = 'ACTIONABLE_WITH_EVIDENCE' | 'EDUCATIONAL_ONLY'

export interface AdvisoryCitation {
  source_id: string
  title: string
  authority: string
  url: string
  retrieved_date: string
  reliability_tier: string
  verification_status: string
  provenance_sha256: string | null
  chunk_refs: string[]
  record_ids: string[]
}

export interface AdvisoryEvidence {
  chunk_ref: string
  chunk_type: string
  score: number
  approved_use_id: string | null
  advisory_status: AdvisoryStatus | null
}

export interface SafetyDisclosure {
  field: 'phi' | 'rei' | 'ppe'
  status: 'PUBLISHED' | 'NOT_PUBLISHED_IN_SOURCE'
  value: string | null
  note: string | null
}

export interface RuleFinding {
  rule_id: string
  code: string
  severity: 'block' | 'restrict_actionability' | 'warn'
  action: string
  message: string
  detail: Record<string, unknown>
}

export interface AdvisorySection {
  heading?: string
  items?: string[]
}

export interface UsagePolicy {
  is_pesticide_recommendation: boolean
  is_regulatory_approval: boolean
  may_state_dosage_as_authoritative: boolean
  must_show_citations: boolean
  educational_only: boolean
}

export interface AdvisoryResponse {
  query: string
  answer_language: 'en' | 'hi'
  outcome: AdvisoryOutcome
  answer: string | null
  sections: AdvisorySection[]
  message: string | null
  answer_scope: 'record' | 'crop'
  citations: AdvisoryCitation[]
  evidence: AdvisoryEvidence[]
  safety_disclosures: SafetyDisclosure[]
  advisory_status: AdvisoryStatus | null
  rule_findings: RuleFinding[]
  rule_trace: Record<string, unknown>
  decision: AdvisoryDecision | null
  missing_information: string[]
  confidence: number
  confidence_label: 'low' | 'medium' | 'high'
  confidence_components: Record<string, unknown>
  classification: Record<string, unknown>
  generation_mode: 'extractive'
  model_versions: Record<string, string>
  usage_policy: UsagePolicy
}

export interface RagStatusResponse {
  vector_backend: string
  embedding_model: string
  indexed_chunks: number
  repository_backend: string | null
  classifier_version: string
  generation_mode: string
  thresholds: Record<string, number>
}

/** Evaluation-only shapes: served by /classification/model-info and /knowledge-base/status. */
export interface ModelInfoResponse {
  model_version: string
  trained_at: string | null
  classifier_type: string
  targets: Record<string, string[]>
  thresholds: Record<string, Record<string, number>>
  training_metadata: Record<string, unknown>
  note: string
}

export interface KnowledgeBaseStatusResponse {
  repository_backend: string | null
  repository_configured: string | null
  repository_class: string | null
  repository_fallback_reason: string | null
  kb_repository_env_var: string
  records: Record<string, unknown> | null
  vector_store: Record<string, unknown>
}

export interface RulesStatusResponse {
  engine: string
  generation_involvement: string
  rules: Array<{
    rule_id: string
    name: string
    trigger: string
    action: string
    severity: string
  }>
  block_precedence: string[]
  thresholds: Record<string, number>
  knowledge_base: {
    records: number
    actionable_with_evidence: number
    educational_only: number
    actionable_record_ids: string[]
    safety_profile_complete?: number
    regulatory_verifications_recorded?: number
    reason: string
  }
}
