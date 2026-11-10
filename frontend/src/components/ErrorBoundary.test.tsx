/**
 * The render-error boundary.
 *
 * The child in these tests throws during render on purpose. What is asserted is
 * the contract the brief asks for: a branded fallback instead of a blank page, a
 * working reload, nothing internal on screen — and that a healthy tree renders
 * through the boundary untouched.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ErrorBoundary } from './ErrorBoundary'
import { REGISTRATION_NUMBER } from '../test/academicIdentifiers'

/** Throws during render, like the nested-object bug that blanked /evaluation. */
function ThrowingChild({ message = `kaput — internal detail ${REGISTRATION_NUMBER}` }: { message?: string }) {
  throw new Error(message)
}

function Bomb(): JSX.Element {
  return <ThrowingChild />
}

let consoleError: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  // React logs the caught error itself; keep the test output readable while
  // still being able to assert on our own logging.
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  window.localStorage.clear()
})

afterEach(() => {
  consoleError.mockRestore()
  vi.restoreAllMocks()
})

/** jsdom gives `location.reload` no implementation and it is not writable. */
function stubReload() {
  const reload = vi.fn()
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: { ...window.location, reload },
  })
  return reload
}

describe('ErrorBoundary', () => {
  it('shows a branded fallback instead of a blank page when a child throws', () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )

    const fallback = screen.getByTestId('error-fallback')
    expect(fallback).toHaveAttribute('role', 'alert')
    expect(screen.getByRole('heading', { level: 1, name: 'Something went wrong' })).toBeInTheDocument()
    expect(screen.getByText('Krishi Salah')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload the page' })).toBeInTheDocument()
    expect(screen.queryByText(/kaput/)).not.toBeInTheDocument()
  })

  it('keeps stack traces, file paths and the thrown message off the screen', () => {
    const { container } = render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )

    const text = container.textContent ?? ''
    for (const leak of [
      'kaput',
      REGISTRATION_NUMBER,
      'at ThrowingChild',
      '.tsx',
      'ErrorBoundary',
      'componentStack',
      'node_modules',
    ]) {
      expect(text).not.toContain(leak)
    }
  })

  it('reloads the page from the fallback button', async () => {
    const reload = stubReload()
    const user = userEvent.setup()

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )

    expect(reload).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Reload the page' }))
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('renders normal children unchanged, with no fallback in the tree', () => {
    render(
      <ErrorBoundary>
        <p>An ordinary page</p>
      </ErrorBoundary>,
    )

    expect(screen.getByText('An ordinary page')).toBeInTheDocument()
    expect(screen.queryByTestId('error-fallback')).not.toBeInTheDocument()
  })

  it('logs the error for developers without putting it in the interface', () => {
    render(
      <ErrorBoundary>
        <Bomb message="diagnostic detail" />
      </ErrorBoundary>,
    )

    const logged = consoleError.mock.calls.map((call) => call.join(' ')).join('\n')
    expect(logged).toContain('[Krishi Salah] render error')
    expect(screen.getByTestId('error-fallback').textContent).not.toContain('diagnostic detail')
  })

  it('honours the saved Hindi choice even before <html lang> is set', () => {
    // The crash can happen on the first render, before LanguageProvider's
    // effect has mirrored the choice onto the document.
    window.localStorage.setItem('pesticide-advisory-language', 'hi')
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'कुछ गड़बड़ हो गई' })).toBeInTheDocument()
  })

  it('defaults to English when no choice is recorded', () => {
    document.documentElement.lang = 'en'
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Something went wrong' })).toBeInTheDocument()
  })

  it('speaks Hindi when the page is Hindi, without needing the i18n provider', () => {
    document.documentElement.lang = 'hi'
    try {
      render(
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>,
      )
      expect(screen.getByRole('heading', { level: 1, name: 'कुछ गड़बड़ हो गई' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'पृष्ठ फिर से लोड करें' })).toBeInTheDocument()
    } finally {
      document.documentElement.lang = 'en'
    }
  })
})
