/**
 * API client behaviour.
 *
 * The client is the one place that decides what a user sees when a request
 * fails, so the four failure shapes the backend can actually produce are pinned
 * here: our own {error:{message}}, FastAPI's {detail:[...]} validation errors,
 * a plain-text error body, and a network failure. A rejected request must never
 * be reported as "the service is down", and a network failure must not look
 * like an answer.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, API_BASE_URL, apiClient } from './apiClient'

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const spy = vi.fn().mockResolvedValue(response as Response)
  vi.stubGlobal('fetch', spy)
  return spy
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiClient.get', () => {
  it('returns the parsed body on success', async () => {
    mockFetch({ ok: true, status: 200, json: async () => ({ status: 'ok' }) })
    await expect(apiClient.get<{ status: string }>('/health')).resolves.toEqual({ status: 'ok' })
  })

  it('requests the configured base URL', async () => {
    const spy = mockFetch({ ok: true, status: 200, json: async () => ({}) })
    await apiClient.get('/health')
    expect(spy).toHaveBeenCalledWith(`${API_BASE_URL}/health`, undefined)
  })

  it("surfaces the backend's own {error:{message}} shape", async () => {
    mockFetch({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
      json: async () => ({ error: { status_code: 503, message: 'Vector store unavailable' } }),
    })
    await expect(apiClient.get('/rag/status')).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'Vector store unavailable',
    })
  })

  it('joins FastAPI validation messages instead of showing a 422 as an outage', async () => {
    mockFetch({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      json: async () => ({
        detail: [
          { loc: ['body', 'query'], msg: 'field required' },
          { loc: ['body', 'max_evidence'], msg: 'must be <= 10' },
        ],
      }),
    })
    const error = await apiClient.get('/rag/answer').catch((err: unknown) => err as ApiError)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(422)
    expect(error.message).toBe('field required; must be <= 10')
  })

  it('falls back to statusText when the error body is not JSON', async () => {
    mockFetch({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    })
    await expect(apiClient.get('/health')).rejects.toMatchObject({ status: 502, message: 'Bad Gateway' })
  })

  it('reports a network failure as unreachable, with no status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = (await apiClient.get('/health').catch((err: unknown) => err)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBeUndefined()
    expect(error.message).toContain('Could not reach the backend')
  })
})

describe('apiClient.post', () => {
  it('sends JSON with the method and content type the backend expects', async () => {
    const spy = mockFetch({ ok: true, status: 200, json: async () => ({ outcome: 'answered' }) })
    await apiClient.post('/rag/answer', { query: 'cotton pink bollworm' })
    const init = spy.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body as string)).toEqual({ query: 'cotton pink bollworm' })
  })
})
