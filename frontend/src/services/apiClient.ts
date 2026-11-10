/**
 * Central API service (Task 4). All backend calls go through this module
 * so the base URL and error handling live in exactly one place.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch (err) {
    // Network-level failure: backend unreachable, CORS blocked, DNS, etc.
    throw new ApiError(
      `Could not reach the backend at ${API_BASE_URL}. Is it running? (${(err as Error).message})`,
    )
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      // The backend's own handlers use {error: {message}}; FastAPI's built-in
      // validation failures use {detail: ...}. Both are surfaced, because a
      // rejected request must not look like a service outage.
      detail =
        body?.error?.message ??
        (typeof body?.detail === 'string'
          ? body.detail
          : Array.isArray(body?.detail)
            ? body.detail.map((item: { msg?: string }) => item?.msg ?? '').filter(Boolean).join('; ')
            : undefined) ??
        detail
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as T
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}

export { API_BASE_URL }
