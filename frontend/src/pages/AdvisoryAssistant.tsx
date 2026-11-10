import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { AdvisoryComposer } from '../components/AdvisoryComposer'
import { AdvisoryResult } from '../components/AdvisoryResult'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Icon } from '../components/Icon'
import { useLanguage } from '../i18n/LanguageProvider'
import { ApiError } from '../services/apiClient'
import { advisoryService } from '../services/advisoryService'
import type { AdvisoryResponse } from '../types/api'

type Status = 'idle' | 'loading' | 'error' | 'ready'

/** Skeleton shaped like a real answer, so the page does not jump when it lands. */
function LoadingState() {
  const { t } = useLanguage()
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      <Card className="p-5">
        <div className="flex items-start gap-4">
          <div className="h-10 w-10 animate-pulse rounded-full bg-ivory-200" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-44 animate-pulse rounded bg-ivory-200" />
            <div className="h-3 w-3/4 animate-pulse rounded bg-ivory-100" />
          </div>
        </div>
        <p className="mt-4 flex items-center gap-2 text-xs text-ink-500">
          <Icon name="search" className="h-4 w-4 animate-pulse text-forest-600" />
          {t('advisory.submitting')}
        </p>
      </Card>
      <Card className="space-y-3 p-5">
        <div className="h-3 w-24 animate-pulse rounded bg-ivory-200" />
        <div className="h-4 w-full animate-pulse rounded bg-ivory-100" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-ivory-100" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-ivory-100" />
      </Card>
    </div>
  )
}

function EmptyState() {
  const { t } = useLanguage()
  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-sage-200 text-forest-800">
          <Icon name="chat" className="h-5 w-5" />
        </span>
        <div>
          <h2 className="font-display text-[15px] font-semibold text-ink-900">
            {t('advisory.empty.title')}
          </h2>
          <p className="mt-1 max-w-xl text-sm leading-6 text-ink-500">
            {t('advisory.empty.body')}
          </p>
        </div>
      </div>
    </Card>
  )
}

export function AdvisoryAssistant() {
  const { t, choice } = useLanguage()
  const location = useLocation()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<AdvisoryResponse | null>(null)
  const [error, setError] = useState<{ message: string; status?: number } | null>(null)
  const resultRef = useRef<HTMLDivElement | null>(null)
  const consumedState = useRef(false)

  async function submit(text: string) {
    const trimmed = text.trim()
    if (!trimmed || status === 'loading') return
    setStatus('loading')
    setError(null)
    try {
      const response = await advisoryService.ask(trimmed, {
        language: choice === 'auto' ? undefined : choice,
      })
      setResult(response)
      setStatus('ready')
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      )
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null
      setError({
        message: apiError?.message ?? 'Unexpected error while contacting the advisory service.',
        status: apiError?.status,
      })
      setResult(null)
      setStatus('error')
    }
  }

  // The home page hands its question over through router state, so "ask on the
  // home page" really does ask — it does not ask the farmer to type it twice.
  useEffect(() => {
    if (consumedState.current) return
    const handed = (location.state as { query?: string } | null)?.query
    if (!handed) return
    consumedState.current = true
    setQuery(handed)
    void submit(handed)
    // submit is stable for this purpose; it closes over setState only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  const unavailable = error?.status === 503 || error?.status === undefined

  return (
    /* One reading column: a 1.3m-wide answer is harder to follow than a narrow
       one, and the evidence tables scroll inside their own card. */
    <div className="mx-auto max-w-4xl">
      <header className="mb-5 max-w-2xl sm:mb-6">
        <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-forest-700">
          {t('nav.advisory')}
        </p>
        <h1 className="mt-2 text-[27px] font-semibold leading-tight tracking-tight text-ink-900 sm:text-[34px]">
          {t('advisory.title')}
        </h1>
        <p className="mt-2 text-sm leading-6 text-ink-600">{t('advisory.subtitle')}</p>
      </header>

      <AdvisoryComposer
        value={query}
        onChange={setQuery}
        onSubmit={submit}
        busy={status === 'loading'}
      />

      <div ref={resultRef} className="mt-5 scroll-mt-24">
        {status === 'loading' && <LoadingState />}

        {status === 'error' && error && (
          <Card className="border-danger-200 p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-danger-50 text-danger-600">
                <Icon name="alert" className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <h2 className="font-display text-[15px] font-semibold text-ink-900">
                  {t('advisory.error.title')}
                </h2>
                <p className="mt-1 text-sm leading-6 text-ink-700">
                  {unavailable ? t('advisory.error.unavailable') : error.message}
                </p>
                <p className="mt-1.5 break-words font-mono text-2xs text-ink-500">
                  {error.status ? `HTTP ${error.status} · ` : 'network · '}
                  {error.message}
                </p>
                <Button
                  variant="secondary"
                  className="mt-3"
                  onClick={() => void submit(query)}
                >
                  {t('advisory.error.retry')}
                </Button>
              </div>
            </div>
          </Card>
        )}

        {status === 'idle' && <EmptyState />}

        {status === 'ready' && result && <AdvisoryResult response={result} />}
      </div>
    </div>
  )
}
