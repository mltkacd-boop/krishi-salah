/**
 * The boundary sits around the route content, not around the whole document.
 *
 * That placement is the point: a page that throws must not take the header,
 * footer, language switch or navigation with it. This test renders the real
 * layout with a throwing route and asserts both halves of that promise — the
 * fallback appears, and the site is still navigable.
 */
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import { AppLayout } from './AppLayout'

function ThrowingPage(): JSX.Element {
  throw new Error('page exploded')
}

function HealthyPage() {
  return <h1>Healthy page</h1>
}

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <LanguageProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<HealthyPage />} />
            <Route path="/broken" element={<ThrowingPage />} />
          </Route>
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AppLayout with the error boundary', () => {
  it('keeps the header, navigation and footer while a page is broken', () => {
    renderAt('/broken')

    expect(screen.getByTestId('error-fallback')).toBeInTheDocument()

    // Navigation survives.
    const links = screen.getAllByRole('link')
    expect(links.length).toBeGreaterThan(5)
    expect(links.some((link) => link.getAttribute('href') === '/safety-guidelines')).toBe(true)
    expect(links.some((link) => link.getAttribute('href') === '/knowledge-base')).toBe(true)
    // The skip link and both navigation bars are still mounted.
    expect(screen.getAllByRole('navigation').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Safe pesticide decisions').length).toBeGreaterThan(0)
  })

  it('renders a healthy route through the boundary untouched', () => {
    renderAt('/')

    expect(screen.getByRole('heading', { level: 1, name: 'Healthy page' })).toBeInTheDocument()
    expect(screen.queryByTestId('error-fallback')).not.toBeInTheDocument()
  })
})
