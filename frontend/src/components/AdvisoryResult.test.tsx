/**
 * What a farmer sees versus what an evaluator sees.
 *
 * The product rule is that the ordinary result view contains no decision codes,
 * rule identifiers, retrieval scores or record ids: those live in the collapsed
 * technical section, and they never carry a safety fact that is absent from the
 * visible part of the answer.
 *
 * These assertions are deliberately negative — `queryByText` for the internal
 * strings — because the failure mode is a diagnostic leaking back into the
 * interface, not a missing label.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import type { AdvisoryResponse } from '../types/api'
import { AdvisoryResult } from './AdvisoryResult'

const RESPONSE: AdvisoryResponse = {
  query: 'How do I control pink bollworm in cotton?',
  answer_language: 'en',
  outcome: 'answered',
  answer: 'Recorded measures for Pink bollworm in Cotton, as described by the cited source.',
  sections: [{ heading: 'Safety information in this record', items: ['Not published in the source.'] }],
  message: null,
  answer_scope: 'record',
  citations: [
    {
      source_id: 'src-tnau-cotton',
      title: 'Crop Protection — Cotton — Pink bollworm',
      authority: 'Tamil Nadu Agricultural University',
      url: 'https://example.org/cotton',
      retrieved_date: '2026-10-01',
      reliability_tier: 'state_agricultural_university',
      verification_status: 'VERIFIED_SOURCE_RECOMMENDATION',
      provenance_sha256: 'SHA256ZZZ',
      chunk_refs: ['chunk-zzz'],
      record_ids: ['au-zzz'],
    },
  ],
  evidence: [
    {
      chunk_ref: 'chunk-zzz',
      chunk_type: 'record_summary',
      score: 0.4242,
      approved_use_id: 'au-zzz',
      advisory_status: 'EDUCATIONAL_ONLY',
    },
  ],
  safety_disclosures: [
    { field: 'phi', status: 'NOT_PUBLISHED_IN_SOURCE', value: null, note: 'The page states no PHI.' },
    { field: 'rei', status: 'NOT_PUBLISHED_IN_SOURCE', value: null, note: 'The page states no REI.' },
    { field: 'ppe', status: 'NOT_PUBLISHED_IN_SOURCE', value: null, note: 'The page states no PPE.' },
  ],
  advisory_status: 'EDUCATIONAL_ONLY',
  rule_findings: [
    {
      rule_id: 'R2_REQUIRE_SAFETY_FIELDS',
      code: 'phi_not_published',
      severity: 'restrict_actionability',
      action: 'RESTRICT_TO_EDUCATIONAL',
      message: 'The record does not publish every safety value, so it is shown as educational only.',
      detail: {},
    },
  ],
  rule_trace: { decision: 'EDUCATIONAL_INFORMATION', gate_detail: 'none' },
  decision: 'EDUCATIONAL_INFORMATION',
  missing_information: ['phi', 'rei', 'ppe'],
  confidence: 0.6123,
  confidence_label: 'medium',
  confidence_components: { retrieval: 0.4646, classification: 0.8512 },
  classification: { crop: 'cotton', task: 'pest_control' },
  generation_mode: 'extractive',
  model_versions: { classifier: 'clf-1.0.0', embedder: 'hashing-lexical-v1' },
  usage_policy: {
    is_pesticide_recommendation: false,
    is_regulatory_approval: false,
    may_state_dosage_as_authoritative: false,
    must_show_citations: true,
    educational_only: true,
  },
}

function renderResult(response: AdvisoryResponse = RESPONSE) {
  return render(
    <LanguageProvider>
      <AdvisoryResult response={response} />
    </LanguageProvider>,
  )
}

const INTERNAL_STRINGS = [
  'EDUCATIONAL_INFORMATION',
  'R2_REQUIRE_SAFETY_FIELDS',
  'phi_not_published',
  'RESTRICT_TO_EDUCATIONAL',
  'chunk-zzz',
  'au-zzz',
  'SHA256ZZZ',
  '0.4242',
  'hashing-lexical-v1',
]

describe('AdvisoryResult — ordinary view', () => {
  it('shows the friendly decision class, not the backend enum', () => {
    renderResult()
    // The phrase is reused as a plain severity label in "Why this decision",
    // so it is asserted on the badge itself — the element that also carries the
    // backend's raw class in `data-decision`.
    const badge = document.querySelector('[data-decision="EDUCATIONAL_INFORMATION"]')
    expect(badge).not.toBeNull()
    expect(badge?.textContent).toContain('Educational information only')
    for (const raw of INTERNAL_STRINGS) {
      expect(screen.queryByText(raw)).not.toBeInTheDocument()
    }
  })

  it('shows safety gaps and the source, which are the point of the answer', () => {
    renderResult()
    expect(screen.getByText('Missing information')).toBeInTheDocument()
    expect(screen.getAllByText('Pre-harvest interval (PHI)').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Not published in source').length).toBe(3)
    expect(screen.getByText('Crop Protection — Cotton — Pink bollworm')).toBeInTheDocument()
    expect(screen.getByText('Tamil Nadu Agricultural University · Retrieved 2026-10-01')).toBeInTheDocument()
  })

  it('reports confidence qualitatively, without the blended score or its inputs', () => {
    renderResult()
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.queryByText(/61/)).not.toBeInTheDocument()
    expect(screen.queryByText(/0\.46/)).not.toBeInTheDocument()
  })

  it('names each rule severity in words a farmer can act on', () => {
    const withBothSeverities: AdvisoryResponse = {
      ...RESPONSE,
      rule_findings: [
        ...RESPONSE.rule_findings,
        {
          rule_id: 'R5_STALE_SOURCE_CHECK',
          code: 'source_undated',
          severity: 'warn',
          action: 'WARN_AND_PROCEED',
          message: 'The source publishes no date, so confirm it is still current.',
          detail: {},
        },
      ],
    }
    renderResult(withBothSeverities)

    // The labels the brief asks for, verbatim. "Educational information only"
    // legitimately appears twice: on the decision badge and again as the
    // severity label of the rule that produced it.
    expect(screen.getAllByText('Educational information only').length).toBeGreaterThan(1)
    expect(screen.getByText('Important caution')).toBeInTheDocument()

    // ...and the wording they replaced is gone.
    expect(screen.queryByText('Allows education only')).not.toBeInTheDocument()
    expect(screen.queryByText('Attaches a warning')).not.toBeInTheDocument()

    // The severity is a label, not a replacement for the rule's message.
    expect(
      screen.getByText('The source publishes no date, so confirm it is still current.'),
    ).toBeInTheDocument()
    // The identifier itself stays out of the ordinary view.
    expect(screen.queryByText('R5_STALE_SOURCE_CHECK')).not.toBeInTheDocument()
  })

  it('keeps the reason in plain words while the rule identity stays hidden', () => {
    renderResult()
    expect(
      screen.getByText(
        'The record does not publish every safety value, so it is shown as educational only.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('R2_REQUIRE_SAFETY_FIELDS')).not.toBeInTheDocument()
  })
})

describe('AdvisoryResult — evaluation detail', () => {
  it('reveals the machine-readable trace only when expanded', async () => {
    const user = userEvent.setup()
    renderResult()

    const summary = screen.getByText('Technical details (for evaluation)')
    expect(screen.queryByText('R2_REQUIRE_SAFETY_FIELDS')).not.toBeInTheDocument()

    await user.click(summary)

    expect(screen.getByText('R2_REQUIRE_SAFETY_FIELDS')).toBeInTheDocument()
    expect(screen.getByText('phi_not_published')).toBeInTheDocument()
    expect(screen.getByText('chunk-zzz')).toBeInTheDocument()
    expect(screen.getByText('SHA256ZZZ')).toBeInTheDocument()
  })
})

describe('AdvisoryResult — refusal', () => {
  const refusal: AdvisoryResponse = {
    ...RESPONSE,
    outcome: 'safety_value_not_published',
    decision: 'SAFETY_REFUSAL',
    answer: null,
    sections: [],
    message: 'No source in this knowledge base publishes a PHI value for this record, so I cannot give one.',
    citations: [],
    evidence: [],
    advisory_status: null,
    missing_information: ['phi'],
    rule_findings: [],
    rule_trace: { gate_detail: 'safety_value_not_published' },
  }

  it('leads with the refusal and still says what to do next', () => {
    renderResult(refusal)
    expect(screen.getByText('Cannot provide a safe recommendation')).toBeInTheDocument()
    expect(screen.getByText(/cannot give one/i)).toBeInTheDocument()
    expect(screen.getByText('What to do next')).toBeInTheDocument()
    expect(
      screen.getByText(/Do not spray on the basis of this answer/i),
    ).toBeInTheDocument()
  })

  it('does not render an empty source list for a refusal', () => {
    renderResult(refusal)
    expect(screen.queryByText('No citations — this response did not use a record.')).not.toBeInTheDocument()
  })
})


