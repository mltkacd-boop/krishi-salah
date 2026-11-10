/**
 * Submission metadata is not part of the product.
 *
 * A student's name, registration number, section, course code and project type
 * are coursework bookkeeping. They must not appear on an ordinary page — where a
 * farmer reads the interface — and they must not appear on `/evaluation` either,
 * because that page is for the system under evaluation, not for the submission.
 *
 * The check runs at two levels: the whole string catalogue in both languages
 * (so a translation cannot reintroduce them), and the two pages that used to
 * carry them, in English and Hindi.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import { STRINGS } from '../i18n/strings'
import { REGISTRATION_NUMBER, SECTION_CODE } from '../test/academicIdentifiers'
import { Evaluation } from '../pages/Evaluation'
import { ProjectInfo } from '../pages/ProjectInfo'

/** Values and labels that must never be rendered. */
const FORBIDDEN = [
  'Himanshu',
  REGISTRATION_NUMBER,
  SECTION_CODE,
  'CSE 276',
  'Group Project',
  'Registration number',
  'Project type',
  'Student',
  'Section',
  'Course',
]

vi.mock('../services/knowledgeBaseService', () => ({
  knowledgeBaseService: {
    getCrops: () => Promise.resolve([{ crop_id: 'cotton', crop_name: 'Cotton', is_pilot_crop: true }]),
    getSources: () => Promise.resolve([]),
    getApprovedUses: () => Promise.resolve([{}]),
    status: () => Promise.resolve({ repository_backend: 'json' }),
  },
}))

vi.mock('../services/advisoryService', () => ({
  advisoryService: {
    status: () => Promise.resolve({ vector_backend: 'array', thresholds: {} }),
    rulesStatus: () =>
      Promise.resolve({
        engine: 'deterministic_rules',
        generation_involvement: 'none',
        rules: [],
        block_precedence: [],
        thresholds: {},
        knowledge_base: { records: 9, actionable_with_evidence: 0, educational_only: 9, reason: '—' },
      }),
  },
}))

vi.mock('../services/classificationService', () => ({
  classificationService: {
    modelInfo: () =>
      Promise.resolve({
        model_version: 'clf-1.0.0',
        targets: {},
        thresholds: {},
        training_metadata: {},
        note: '—',
      }),
  },
}))

function renderAt(node: React.ReactNode) {
  return render(
    <MemoryRouter>
      <LanguageProvider>{node}</LanguageProvider>
    </MemoryRouter>,
  )
}

function expectClean(text: string) {
  for (const token of FORBIDDEN) {
    expect(text, `"${token}" must not be rendered`).not.toContain(token)
  }
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  window.localStorage.clear()
})

describe('submission metadata', () => {
  it('is absent from the whole string catalogue, in both languages', () => {
    for (const lang of ['en', 'hi'] as const) {
      const text = Object.entries(STRINGS[lang])
        .map(([key, value]) => `${key} ${value}`)
        .join('\n')
      expectClean(text)
    }
  })

  it('is absent from the About page in English', async () => {
    const { container } = renderAt(<ProjectInfo />)
    await waitFor(() => expect(screen.getByText('Cotton')).toBeInTheDocument())
    expectClean(container.textContent ?? '')
  })

  it('is absent from the About page in Hindi', async () => {
    window.localStorage.setItem('pesticide-advisory-language', 'hi')
    const { container } = renderAt(<ProjectInfo />)
    await waitFor(() => expect(screen.getByText('Cotton')).toBeInTheDocument())
    expect(document.documentElement.lang).toBe('hi')
    expectClean(container.textContent ?? '')
  })

  it('is absent from the evaluation page in English, which keeps the project title', async () => {
    const { container } = renderAt(<Evaluation />)
    await waitFor(() => expect(screen.getByText('Project record')).toBeInTheDocument())
    expect(
      screen.getByText('Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support'),
    ).toBeInTheDocument()
    expectClean(container.textContent ?? '')
  })

  it('is absent from the evaluation page in Hindi', async () => {
    window.localStorage.setItem('pesticide-advisory-language', 'hi')
    const { container } = renderAt(<Evaluation />)
    await waitFor(() => expect(screen.getByText('परियोजना विवरण')).toBeInTheDocument())
    expectClean(container.textContent ?? '')
  })
})
