/**
 * Advisory error handling.
 *
 * What matters here is the distinction the user must be able to make:
 *
 *   - backend down            -> "the service did not respond"
 *   - backend refused (503)   -> also unavailable, because nothing was decided
 *   - request rejected (4xx)  -> the backend's reason, verbatim
 *
 * None of these may look like a safety refusal, and none may look like an
 * answer. The service is mocked at the module boundary because these are
 * frontend branches; the real HTTP path is covered by the Playwright check and
 * the backend suite.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import { ApiError } from '../services/apiClient'
import { AdvisoryAssistant } from './AdvisoryAssistant'

const ask = vi.fn()
const status = vi.fn()

vi.mock('../services/advisoryService', () => ({
  advisoryService: {
    ask: (...args: unknown[]) => ask(...args),
    status: (...args: unknown[]) => status(...args),
    rulesStatus: vi.fn(),
  },
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <LanguageProvider>
        <AdvisoryAssistant />
      </LanguageProvider>
    </MemoryRouter>,
  )
}

async function askQuestion(text = 'How do I control pink bollworm in cotton?') {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Your question'), text)
  await user.click(screen.getByRole('button', { name: /Get guidance/i }))
}

afterEach(() => {
  ask.mockReset()
  status.mockReset()
})

describe('AdvisoryAssistant', () => {
  it('passes the question and no language override while the interface is on "auto"', async () => {
    status.mockResolvedValue({
      vector_backend: 'array',
      embedding_model: 'hashing-lexical-v1',
      indexed_chunks: 60,
      repository_backend: 'postgres',
      classifier_version: 'clf-v1',
      generation_mode: 'extractive',
      thresholds: {},
    })
    ask.mockRejectedValue(new ApiError('nope', 500))
    renderPage()
    await askQuestion()

    await waitFor(() => expect(ask).toHaveBeenCalledTimes(1))
    const [query, options] = ask.mock.calls[0] as [string, Record<string, unknown>]
    // The whole payload is built by the service as {query, max_evidence}; the
    // page contributes only the question and, when the user pinned a language,
    // that language. A decision, status or verification field here would be a
    // client-side override, and the backend rejects unknown fields outright.
    expect(query).toBe('How do I control pink bollworm in cotton?')
    expect(options).toEqual({})
  })

  it('shows an unreachable notice, and no decision badge, when the network fails', async () => {
    status.mockRejectedValue(new ApiError('offline'))
    ask.mockRejectedValue(new ApiError('Could not reach the backend at http://localhost:8000. Is it running?'))
    renderPage()
    await askQuestion()

    expect(await screen.findByText('The advisory service did not respond')).toBeInTheDocument()
    expect(screen.getAllByText(/unavailable/i).length).toBeGreaterThan(0)
    // No decision was made, so none may be shown.
    expect(document.querySelector('[data-decision]')).toBeNull()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('treats a 503 as unavailable rather than as a safety decision', async () => {
    status.mockRejectedValue(new ApiError('offline'))
    ask.mockRejectedValue(new ApiError('Vector store unavailable', 503))
    renderPage()
    await askQuestion()

    expect(await screen.findByText('The advisory service did not respond')).toBeInTheDocument()
    expect(screen.getAllByText(/unavailable/i).length).toBeGreaterThan(0)
    expect(document.querySelector('[data-decision]')).toBeNull()
  })

  it("shows the backend's own reason for a rejected request", async () => {
    status.mockRejectedValue(new ApiError('offline'))
    ask.mockRejectedValue(new ApiError('Extra inputs are not permitted', 422))
    renderPage()
    await askQuestion()

    expect(await screen.findByText('The advisory service did not respond')).toBeInTheDocument()
    expect(screen.getAllByText(/Extra inputs are not permitted/).length).toBeGreaterThan(0)
    expect(screen.getByText(/HTTP 422/)).toBeInTheDocument()
  })

  it('retries the same question without inventing an answer', async () => {
    status.mockRejectedValue(new ApiError('offline'))
    ask.mockRejectedValueOnce(new ApiError('boom', 500)).mockRejectedValueOnce(new ApiError('boom', 500))
    renderPage()
    await askQuestion()
    await screen.findByRole('button', { name: 'Try again' })

    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(ask).toHaveBeenCalledTimes(2))
  })
})


