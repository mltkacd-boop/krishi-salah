/**
 * The evaluation view is where the technical diagnostics live now.
 *
 * Two things to hold: it must actually render them (the payloads contain
 * nested objects, which are not valid React children — the first version of
 * this page crashed on exactly that), and it must not carry identifiers that
 * belong to a student submission rather than to the system under test.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import { REGISTRATION_NUMBER, SECTION_CODE } from '../test/academicIdentifiers'
import { Evaluation } from './Evaluation'

const ragStatus = vi.fn()
const rulesStatus = vi.fn()
const modelInfo = vi.fn()
const kbStatus = vi.fn()

vi.mock('../services/advisoryService', () => ({
  advisoryService: {
    status: () => ragStatus(),
    rulesStatus: () => rulesStatus(),
  },
}))

vi.mock('../services/classificationService', () => ({
  classificationService: { modelInfo: () => modelInfo() },
}))

vi.mock('../services/knowledgeBaseService', () => ({
  knowledgeBaseService: { status: () => kbStatus() },
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <Evaluation />
      </LanguageProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  ragStatus.mockReset()
  rulesStatus.mockReset()
  modelInfo.mockReset()
  kbStatus.mockReset()
})

describe('Evaluation', () => {
  it('renders the diagnostics, including nested threshold objects', async () => {
    ragStatus.mockResolvedValue({
      vector_backend: 'array',
      embedding_model: 'hashing-lexical-v1',
      indexed_chunks: 60,
      repository_backend: 'JSONFileKnowledgeBaseRepository',
      classifier_version: 'clf-1.0.0',
      generation_mode: 'extractive',
      thresholds: {
        min_chunk_similarity: 0.05,
        // Nested: the classifier has one threshold set per target head.
        classifier_min_confidence: { crop: 0.4, task: 0.4, safety_topic: 0.4 },
      },
    })
    rulesStatus.mockResolvedValue({
      engine: 'deterministic_rules',
      generation_involvement: 'none',
      rules: [
        {
          rule_id: 'R2_REQUIRE_SAFETY_FIELDS',
          name: 'RequireSafetyFields',
          trigger: 'PHI, REI or PPE is missing.',
          action: 'ESCALATE_MISSING_INFO',
          severity: 'restrict_actionability',
        },
      ],
      block_precedence: ['R2_REQUIRE_SAFETY_FIELDS'],
      thresholds: { min_classifier_confidence: 0.4 },
      knowledge_base: {
        records: 9,
        actionable_with_evidence: 0,
        educational_only: 9,
        reason: 'No record has a complete published safety profile.',
      },
    })
    modelInfo.mockResolvedValue({
      model_version: 'clf-1.0.0',
      trained_at: '2026-11-02T20:37:45+00:00',
      classifier_type: 'TF-IDF with logistic regression',
      targets: { crop: ['rice', 'cotton', 'no_crop'], task: ['pest_management'] },
      thresholds: { crop: { min_confidence: 0.4, min_margin: 0.15 } },
      training_metadata: { dataset_rows: 211, split_seed: 42 },
      note: 'Labels are intent signals.',
    })
    kbStatus.mockResolvedValue({
      repository_backend: 'json',
      repository_configured: 'json',
      repository_class: 'JSONFileKnowledgeBaseRepository',
      repository_fallback_reason: null,
      kb_repository_env_var: 'KB_REPOSITORY',
      records: { crops: 5, sources: 8, approved_uses: 9 },
      vector_store: { backend: 'array', chunks: 60 },
    })

    renderPage()

    // The id appears twice by design: once in the rule table, once in the
    // block precedence order.
    await waitFor(() =>
      expect(screen.getAllByText('R2_REQUIRE_SAFETY_FIELDS').length).toBeGreaterThan(1),
    )

    // The nested objects are flattened, not printed as [object Object].
    expect(screen.getByText('crop 0.4 · task 0.4 · safety_topic 0.4')).toBeInTheDocument()
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument()
    expect(screen.getAllByText('clf-1.0.0').length).toBeGreaterThan(0)
    expect(screen.getByText('extractive')).toBeInTheDocument()
    expect(screen.getByText('hashing-lexical-v1')).toBeInTheDocument()

    const text = document.body.textContent ?? ''
    expect(text).not.toMatch(/password|postgres(ql)?:\/\/|api[_-]?key/i)
  })

  it('shows the technical project title but no submission metadata', async () => {
    ragStatus.mockRejectedValue(new Error('down'))
    rulesStatus.mockRejectedValue(new Error('down'))
    modelInfo.mockRejectedValue(new Error('down'))
    kbStatus.mockRejectedValue(new Error('down'))

    renderPage()

    await waitFor(() => expect(screen.getByText(/Project record/)).toBeInTheDocument())

    expect(
      screen.getByText(
        'Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support',
      ),
    ).toBeInTheDocument()

    // Student, section, course and project type belong to the coursework, not
    // to the system under evaluation.
    const text = document.body.textContent ?? ''
    for (const value of [
      'Himanshu',
      REGISTRATION_NUMBER,
      SECTION_CODE,
      'CSE 276',
      'Group Project',
    ]) {
      expect(text).not.toContain(value)
    }
    for (const label of ['Student', 'Section', 'Course', 'Project type']) {
      expect(text).not.toContain(label)
    }

    // One failed call must not blank the page.
    expect(screen.getByText(/Could not load diagnostics/)).toBeInTheDocument()
  })
})
