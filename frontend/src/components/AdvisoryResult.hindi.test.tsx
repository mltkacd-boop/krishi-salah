/**
 * Hindi localisation of farmer-facing response content.
 *
 * The failure this guards: with the interface on "follow my question", the
 * backend answers in Hindi but the result chrome was rendered from the
 * *interface* language — so a Hindi PHI refusal appeared under English headings
 * ("Missing information", "What to do next", "Why this decision"), with English
 * safety instructions and a "ConfidenceLow" caption.
 *
 * The rule asserted here: a Hindi answer is entirely Hindi in the farmer-facing
 * view, an English answer is unchanged, and the technical section keeps the
 * machine-readable fields untranslated in both cases.
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import type { AdvisoryResponse } from '../types/api'
import { AdvisoryResult } from './AdvisoryResult'

/** Farmer-facing English headings and instructions that must not frame a Hindi answer. */
const ENGLISH_FARMER_STRINGS = [
  'Missing information',
  'Without these, nothing in this answer may be treated as an actionable instruction.',
  'What to do next',
  'Why this decision',
  'Answer language',
  'Sources',
  'Safety data for this record',
  'Do not spray on the basis of this answer.',
  'Pre-harvest interval (PHI)',
  'Re-entry interval (REI)',
  'Protective equipment (PPE)',
  'Cannot provide a safe recommendation',
  'Not published in source',
  'Educational information only',
  'Learning only',
  'Medium',
]

const PHI_QUESTION = 'कपास पर छिड़काव के बाद कटाई में कितने दिन'

/** The live Hindi PHI refusal, as the backend returns it. */
const HINDI_REFUSAL: AdvisoryResponse = {
  query: PHI_QUESTION,
  answer_language: 'hi',
  outcome: 'safety_value_not_published',
  answer: null,
  sections: [],
  message:
    'इस ज्ञान-आधार के किसी स्रोत में इस रिकॉर्ड के लिए PHI, REI या PPE मान नहीं दिया गया है, इसलिए मैं यह नहीं बता सकता।',
  answer_scope: 'record',
  citations: [],
  evidence: [],
  safety_disclosures: [],
  advisory_status: null,
  rule_findings: [],
  rule_trace: { gate_detail: 'safety_value_not_published' },
  decision: 'SAFETY_REFUSAL',
  missing_information: ['phi'],
  confidence: 0.4231,
  confidence_label: 'low',
  confidence_components: { retrieval: 0.31, classification: 0.72 },
  classification: { crop: 'cotton', task: 'pest_management' },
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

/** The same refusal in English, unchanged by this work. */
const ENGLISH_REFUSAL: AdvisoryResponse = {
  ...HINDI_REFUSAL,
  query: 'how long before I can harvest after spraying cotton',
  answer_language: 'en',
  message:
    'No source in this knowledge base publishes a PHI value for this record, so I cannot give one.',
  rule_trace: { gate_detail: 'safety_value_not_published' },
}

/** A Hindi educational answer: safety gaps published, nothing actionable. */
const HINDI_EDUCATIONAL: AdvisoryResponse = {
  ...HINDI_REFUSAL,
  query: 'कपास में गुलाबी सुंडी',
  outcome: 'answered',
  decision: 'EDUCATIONAL_INFORMATION',
  answer: 'स्रोत में दर्ज उपाय नीचे दिए गए हैं।',
  sections: [{ heading: 'फसल और कीट', items: ['कीट: गुलाबी सुंडी'] }],
  message: null,
  advisory_status: 'EDUCATIONAL_ONLY',
  citations: [
    {
      source_id: 'SRC-TNAU-COTTON-PINKBW-01',
      title: 'Cotton — Pink bollworm',
      authority: 'Tamil Nadu Agricultural University',
      url: 'https://example.org/cotton',
      retrieved_date: '2026-10-01',
      reliability_tier: 'state_agricultural_university',
      verification_status: 'VERIFIED_SOURCE_RECOMMENDATION',
      provenance_sha256: 'SHA256ZZZ',
      chunk_refs: ['chunk-zzz'],
      record_ids: ['AU-COTTON-PINK-BOLLWORM-01'],
    },
  ],
  evidence: [
    {
      chunk_ref: 'chunk-zzz',
      chunk_type: 'record_summary',
      score: 0.4242,
      approved_use_id: 'AU-COTTON-PINK-BOLLWORM-01',
      advisory_status: 'EDUCATIONAL_ONLY',
    },
  ],
  // Source-worded notes stay as the source wrote them (English); the labels
  // around them are what the interface localises.
  safety_disclosures: [
    { field: 'phi', status: 'NOT_PUBLISHED_IN_SOURCE', value: null, note: 'The page states no PHI.' },
    { field: 'rei', status: 'NOT_PUBLISHED_IN_SOURCE', value: null, note: 'The page states no REI.' },
    { field: 'ppe', status: 'NOT_PUBLISHED_IN_SOURCE', value: null, note: 'The page states no PPE.' },
  ],
  rule_findings: [
    {
      rule_id: 'R2_REQUIRE_SAFETY_FIELDS',
      code: 'safety_fields_not_published',
      severity: 'restrict_actionability',
      action: 'RESTRICT_TO_EDUCATIONAL',
      message:
        'स्रोत इस रिकॉर्ड के लिए पूरा PHI, REI और PPE विवरण नहीं देता, इसलिए इसे केवल शैक्षिक जानकारी के रूप में दिखाया जा सकता है।',
      detail: {},
    },
  ],
  missing_information: ['phi', 'rei', 'ppe'],
  confidence_label: 'medium',
  confidence: 0.6123,
}

function renderResult(response: AdvisoryResponse, uiLanguage: 'en' | 'hi' = 'en') {
  if (uiLanguage === 'hi') {
    window.localStorage.setItem('pesticide-advisory-language', 'hi')
  } else {
    window.localStorage.removeItem('pesticide-advisory-language')
  }
  return render(
    <LanguageProvider>
      <AdvisoryResult response={response} />
    </LanguageProvider>,
  )
}

function expectNoEnglishFarmerText() {
  for (const text of ENGLISH_FARMER_STRINGS) {
    expect(screen.queryByText(text, { exact: false })).not.toBeInTheDocument()
  }
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('Hindi refusal — farmer-facing content is Hindi', () => {
  it('renders the decision, headings and next steps in Hindi', () => {
    renderResult(HINDI_REFUSAL)

    // Decision badge: the Hindi class name, carried on the same element the
    // backend's raw class is attached to.
    const badge = document.querySelector('[data-decision="SAFETY_REFUSAL"]')
    expect(badge).not.toBeNull()
    expect(badge?.textContent).toContain('सुरक्षित सिफ़ारिश संभव नहीं')

    // Headings that used to leak through in English.
    expect(screen.getByText('अनुपलब्ध जानकारी')).toBeInTheDocument()
    expect(screen.getByText('आगे क्या करें')).toBeInTheDocument()
    expect(screen.getByText('यह निर्णय क्यों')).toBeInTheDocument()

    // The "nothing here is actionable" warning, in Hindi.
    expect(
      screen.getByText('इनके बिना इस उत्तर की कोई भी बात क्रियान्वयन योग्य निर्देश नहीं मानी जाती।'),
    ).toBeInTheDocument()

    // Next-step guidance is Hindi, not the English safety instruction.
    expect(screen.getByText(/इस उत्तर के आधार पर छिड़काव न करें/)).toBeInTheDocument()
    expect(screen.queryByText(/Do not spray on the basis of this answer/)).not.toBeInTheDocument()

    // Answer-language footer reads Hindi in Hindi.
    expect(screen.getByText(/उत्तर की भाषा/)).toBeInTheDocument()
  })

  it('uses the requested PHI / REI / PPE terminology', () => {
    renderResult(HINDI_REFUSAL)
    // The missing-information chip for PHI carries the agreed wording.
    expect(screen.getAllByText('कटाई-पूर्व प्रतीक्षा अवधि (PHI)').length).toBeGreaterThan(0)
  })

  it('leaves no English farmer-facing heading or guidance on screen', () => {
    renderResult(HINDI_REFUSAL)
    expectNoEnglishFarmerText()
  })

  it('contains no English words outside the agreed abbreviations', () => {
    renderResult(HINDI_REFUSAL)
    const root = screen.getByTestId('advisory-result')

    // Drop the evaluation card: it is developer-facing and stays as written.
    const toggle = screen.getByText('Technical details (for evaluation)')
    let node: HTMLElement | null = toggle as HTMLElement
    while (node?.parentElement && node.parentElement !== root) node = node.parentElement
    node?.remove()

    const words = (root.textContent ?? '').match(/[A-Za-z]+/g) ?? []
    // PHI / REI / PPE stay in Latin letters on purpose (requirement: keep the
    // technical abbreviation next to the Hindi term); CIB&RC is a body name.
    const allowed = new Set(['PHI', 'REI', 'PPE', 'CIB', 'RC'])
    expect(words.filter((word) => !allowed.has(word))).toEqual([])
  })

  it('localises the confidence caption and keeps it separate from its value', () => {
    renderResult(HINDI_REFUSAL)
    const caption = screen.getByText('विश्वास')
    const value = screen.getByText('कम')

    expect(caption).toBeInTheDocument()
    expect(value).toBeInTheDocument()
    // Two elements plus a real separator, so the pair cannot render, be read or
    // be copied as one word ("विश्वासकम" / "ConfidenceLow").
    expect(caption).not.toBe(value)
    expect(caption.textContent).not.toContain('कम')
    expect(caption.parentElement?.textContent).toBe('विश्वास: कम')
    expect(screen.queryByText('ConfidenceLow')).not.toBeInTheDocument()
    expect(screen.queryByText('विश्वासकम')).not.toBeInTheDocument()
  })
})

describe('English refusal — unchanged', () => {
  it('still renders the English headings and next steps', () => {
    renderResult(ENGLISH_REFUSAL)

    const badge = document.querySelector('[data-decision="SAFETY_REFUSAL"]')
    expect(badge?.textContent).toContain('Cannot provide a safe recommendation')

    expect(screen.getByText('Missing information')).toBeInTheDocument()
    expect(screen.getByText('What to do next')).toBeInTheDocument()
    expect(screen.getByText('Why this decision')).toBeInTheDocument()
    expect(
      screen.getByText('Without these, nothing in this answer may be treated as an actionable instruction.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Do not spray on the basis of this answer/)).toBeInTheDocument()
    expect(screen.getByText('Low')).toBeInTheDocument()

    // None of the Hindi wording appears for an English answer.
    expect(screen.queryByText('अनुपलब्ध जानकारी')).not.toBeInTheDocument()
    expect(screen.queryByText('आगे क्या करें')).not.toBeInTheDocument()
    expect(screen.queryByText('विश्वास')).not.toBeInTheDocument()
  })
})

describe('Language follows the answer, not the interface chrome', () => {
  it('renders a Hindi answer in Hindi while the interface is English', () => {
    renderResult(HINDI_EDUCATIONAL, 'en')
    expect(screen.getByText('अनुपलब्ध जानकारी')).toBeInTheDocument()
    expect(screen.queryByText('Missing information')).not.toBeInTheDocument()
  })

  it('renders an English answer in English while the interface is Hindi', () => {
    renderResult(ENGLISH_REFUSAL, 'hi')
    expect(screen.getByText('Missing information')).toBeInTheDocument()
    expect(screen.queryByText('अनुपलब्ध जानकारी')).not.toBeInTheDocument()
  })
})

describe('Hindi educational answer — localised, still educational only', () => {
  it('localises the safety section, the policy line and the severity label', () => {
    renderResult(HINDI_EDUCATIONAL)

    expect(screen.getByText('इस रिकॉर्ड का सुरक्षा विवरण')).toBeInTheDocument()
    // Educational-only chip in the safety header.
    expect(screen.getAllByText('केवल शिक्षा').length).toBeGreaterThan(0)
    // The policy line stays a policy line, in Hindi.
    expect(
      screen.getByText(/केवल शैक्षिक जानकारी। यह कीटनाशक सिफ़ारिश नहीं/),
    ).toBeInTheDocument()
    // Safety gaps are still shown, three times, with Hindi labels.
    expect(screen.getAllByText('स्रोत में प्रकाशित नहीं').length).toBe(3)
    expect(screen.getAllByText('कटाई-पूर्व प्रतीक्षा अवधि (PHI)').length).toBeGreaterThan(0)
    expect(
      screen.getAllByText('खेत में दोबारा प्रवेश की प्रतीक्षा अवधि (REI)').length,
    ).toBeGreaterThan(0)
    expect(screen.getAllByText('व्यक्तिगत सुरक्षा उपकरण (PPE)').length).toBeGreaterThan(0)
    // ...and the educational restriction wording stays intact.
    expect(screen.getAllByText('केवल शैक्षिक जानकारी').length).toBeGreaterThan(0)
  })

  it('keeps the source citation and the crop-level answer text', () => {
    renderResult(HINDI_EDUCATIONAL)
    expect(screen.getByText('Cotton — Pink bollworm')).toBeInTheDocument()
    expect(screen.getByText('फसल और कीट')).toBeInTheDocument()
  })

  it('shows no English farmer-facing heading', () => {
    renderResult(HINDI_EDUCATIONAL)
    for (const text of [
      'Missing information',
      'What to do next',
      'Why this decision',
      'Safety data for this record',
      'Sources',
      'Learning only',
      'Published in source',
      'Not published in source',
    ]) {
      expect(screen.queryByText(text, { exact: false })).not.toBeInTheDocument()
    }
  })
})

describe('Technical evaluation detail survives localisation', () => {
  it('keeps the machine-readable fields untranslated for a Hindi answer', async () => {
    const user = userEvent.setup()
    renderResult(HINDI_EDUCATIONAL)

    // Collapsed by default: no diagnostics in the ordinary view.
    expect(screen.queryByText('R2_REQUIRE_SAFETY_FIELDS')).not.toBeInTheDocument()

    // The evaluation section is developer-facing, so it follows the interface
    // language (English here) rather than the answer language — deliberately.
    await user.click(screen.getByText('Technical details (for evaluation)'))

    const panel = document.getElementById('technical-details')
    expect(panel).not.toBeNull()
    const tech = within(panel as HTMLElement)
    // Raw enum values, rule ids, chunk refs, hashes and scores stay as served.
    expect(tech.getByText('EDUCATIONAL_INFORMATION')).toBeInTheDocument()
    expect(tech.getByText('R2_REQUIRE_SAFETY_FIELDS')).toBeInTheDocument()
    expect(tech.getByText('chunk-zzz')).toBeInTheDocument()
    expect(tech.getByText('SHA256ZZZ')).toBeInTheDocument()
    expect(tech.getByText('0.6123')).toBeInTheDocument()
    expect(tech.getByText('hashing-lexical-v1')).toBeInTheDocument()
  })
})
