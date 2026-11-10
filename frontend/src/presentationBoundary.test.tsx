/**
 * Presentation boundary: what must never reach a rendered page.
 *
 * This is deliberately a whole-app test rather than a per-component one. The
 * student's name, registration number, section, course and project type have
 * leaked from shared shells before (a footer line, a page eyebrow), so each
 * route is rendered through the real layout — navigation, footer and all — in
 * both languages, and the rendered text is searched.
 *
 * Services are mocked: this is a test about what the interface prints, not
 * about what the backend returns. The live contract is covered by the Playwright
 * sweep in `backend/scripts/presentation_check.py`.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { LanguageProvider } from './i18n/LanguageProvider'
import { REGISTRATION_NUMBER, SECTION_CODE } from './test/academicIdentifiers'

vi.mock('./services/healthService', () => ({
  healthService: {
    getLiveness: () => Promise.resolve({ status: 'ok', service: 'krishi-salah' }),
    getReadiness: () => Promise.resolve({ status: 'ok', checks: {} }),
  },
}))

vi.mock('./services/knowledgeBaseService', () => ({
  knowledgeBaseService: {
    getCrops: () =>
      Promise.resolve([
        { crop_id: 'cotton', crop_name: 'Cotton', crop_category: 'fibre', is_pilot_crop: true },
      ]),
    getSources: () => Promise.resolve([]),
    getApprovedUses: () =>
      Promise.resolve([
        {
          approved_use_id: 'au-1',
          crop_id: 'cotton',
          target_pest_common_name: 'Pink bollworm',
          target_pest_scientific_name: 'Pectinophora gossypiella',
          economic_threshold_level: null,
          advisory_status: 'EDUCATIONAL_ONLY',
          interventions: [],
          safety_restrictions: {
            phi: { status: 'NOT_PUBLISHED', value: null, note: null },
            rei: { status: 'NOT_PUBLISHED', value: null, note: null },
            ppe: { status: 'NOT_PUBLISHED', value: null, note: null },
          },
        },
      ]),
    status: () =>
      Promise.resolve({
        repository_backend: 'json',
        repository_configured: 'json',
        repository_class: 'JSONFileKnowledgeBaseRepository',
        repository_fallback_reason: null,
        kb_repository_env_var: 'KB_REPOSITORY',
        records: { crops: 5, sources: 8, approved_uses: 9 },
        vector_store: { backend: 'array', chunks: 60 },
      }),
  },
}))

vi.mock('./services/advisoryService', () => ({
  advisoryService: {
    ask: () => Promise.resolve(null),
    status: () =>
      Promise.resolve({
        vector_backend: 'array',
        embedding_model: 'hashing-lexical-v1',
        indexed_chunks: 60,
        repository_backend: 'json',
        classifier_version: 'clf-1.0.0',
        generation_mode: 'extractive',
        thresholds: { min_chunk_similarity: 0.05 },
      }),
    rulesStatus: () =>
      Promise.resolve({
        engine: 'deterministic_rules',
        generation_involvement: 'none',
        rules: [],
        block_precedence: [],
        thresholds: {},
        knowledge_base: {
          records: 9,
          actionable_with_evidence: 0,
          educational_only: 9,
          reason: 'No record publishes a complete safety profile.',
        },
      }),
  },
}))

vi.mock('./services/classificationService', () => ({
  classificationService: {
    modelInfo: () =>
      Promise.resolve({
        model_version: 'clf-1.0.0',
        trained_at: null,
        classifier_type: 'TF-IDF with logistic regression',
        targets: { crop: ['cotton'] },
        thresholds: {},
        training_metadata: {},
        note: 'Labels are intent signals.',
      }),
  },
}))

/** Everything that identifies a submission rather than the system under test. */
const FORBIDDEN = [
  'Himanshu',
  'Yadav',
  REGISTRATION_NUMBER,
  SECTION_CODE,
  'CSE 276',
  'Group Project',
  'Gates Foundation',
  'Registration number',
  'Project type',
]

const ROUTES = [
  ['/', 'Home'],
  ['/advisory', 'Ask assistant'],
  ['/knowledge-base', 'Knowledge library'],
  ['/safety-guidelines', 'Safety guide'],
  ['/project-info', 'About'],
  ['/evaluation', 'Evaluation'],
] as const

const LANGUAGES = [
  ['en', 'English'],
  ['hi', 'Hindi'],
] as const

function renderRoute(route: string, lang: 'en' | 'hi') {
  // LanguageProvider reads the choice from localStorage on mount.
  window.localStorage.setItem('pesticide-advisory-language', lang)
  return render(
    <MemoryRouter initialEntries={[route]}>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  window.localStorage.clear()
})

describe('presentation boundary', () => {
  for (const [lang, langName] of LANGUAGES) {
    for (const [route, routeName] of ROUTES) {
      it(`${routeName} (${langName}) does not render submission metadata`, async () => {
        const { container } = renderRoute(route, lang)

        // Wait for the page to settle so lazily-fetched blocks are mounted too.
        await waitFor(() => expect(container.querySelector('h1')).not.toBeNull())
        await waitFor(() =>
          expect(screen.queryByText(/Loading|लोड हो रही है/)).not.toBeInTheDocument(),
        )

        const text = container.textContent ?? ''
        const leaked = FORBIDDEN.filter((token) => text.includes(token))
        expect(leaked, `leaked on ${route} in ${lang}: ${leaked.join(', ')}`).toEqual([])
      })
    }
  }

  it('keeps the technical project title on the evaluation page', async () => {
    const { container } = renderRoute('/evaluation', 'en')
    await waitFor(() =>
      expect(container.textContent).toContain(
        'Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support',
      ),
    )
  })
})
