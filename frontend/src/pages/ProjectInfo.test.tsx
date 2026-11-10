/**
 * The public About page.
 *
 * Two things are asserted, both negative: the registration number and the
 * academic submission metadata are gone from the public page, and the
 * unverified foundation attribution is gone with them. A positive assertion
 * guards against the page being emptied by accident.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import { REGISTRATION_NUMBER, SECTION_CODE } from '../test/academicIdentifiers'
import { ProjectInfo } from './ProjectInfo'

vi.mock('../services/knowledgeBaseService', () => ({
  knowledgeBaseService: {
    getCrops: () =>
      Promise.resolve([
        { crop_id: 'cotton', crop_name: 'Cotton', crop_category: 'fibre', is_pilot_crop: true },
        { crop_id: 'rice', crop_name: 'Rice', crop_category: 'cereal', is_pilot_crop: true },
      ]),
    getSources: () => Promise.resolve([]),
    getApprovedUses: () => Promise.resolve([{}, {}]),
    status: () => Promise.resolve({}),
  },
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <ProjectInfo />
      </LanguageProvider>
    </MemoryRouter>,
  )
}

describe('ProjectInfo', () => {
  it('introduces the product in user terms', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'About Krishi Salah' })).toBeInTheDocument()
    expect(screen.getByText('What Krishi Salah does')).toBeInTheDocument()
    expect(screen.getByText('Limits of this pilot')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Cotton')).toBeInTheDocument())
  })

  it('carries no registration number or submission metadata', () => {
    const { container } = renderPage()
    const text = container.textContent ?? ''
    expect(text).not.toMatch(new RegExp(REGISTRATION_NUMBER))
    expect(text).not.toMatch(new RegExp(SECTION_CODE))
    expect(text).not.toMatch(/Registration number/i)
    expect(text).not.toMatch(/Group Project/i)
    expect(text).not.toMatch(/Project type/i)
  })

  it('does not repeat the unverified foundation attribution', () => {
    const { container } = renderPage()
    expect(container.textContent ?? '').not.toMatch(/Gates Foundation/i)
  })
})
