import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

import { Icon } from './Icon'

/**
 * A render-error boundary for the main application content.
 *
 * Scope, stated plainly because it matters:
 *
 *   caught      — errors thrown while rendering, in lifecycle methods, and in
 *                 the constructors of the tree below this boundary.
 *   not caught  — rejected promises and other async failures, event-handler
 *                 errors, errors thrown in the boundary's siblings or above it.
 *
 * A failed API call is a normal state in this app, not a crash: services return
 * typed errors and the pages render them. This boundary exists for the case the
 * pages cannot handle — a component that throws mid-render, which previously
 * unmounted the tree and left a blank page.
 */

const COPY = {
  en: {
    brand: 'Krishi Salah',
    tagline: 'Safe pesticide decisions',
    title: 'Something went wrong',
    body: 'This page could not be displayed. Reloading usually fixes it. This is a display fault, not an advisory result — no safety answer was given or withdrawn.',
    action: 'Reload the page',
  },
  hi: {
    brand: 'कृषि सलाह',
    tagline: 'कीटनाशक के सुरक्षित निर्णय',
    title: 'कुछ गड़बड़ हो गई',
    body: 'यह पृष्ठ दिखाया नहीं जा सका। पृष्ठ को फिर से लोड करने से अक्सर समस्या ठीक हो जाती है। यह केवल प्रदर्शन की त्रुटि है, कोई सलाह नहीं — कोई सुरक्षा उत्तर न दिया गया है और न ही वापस लिया गया है।',
    action: 'पृष्ठ फिर से लोड करें',
  },
} as const

/** Must match `STORAGE_KEY` in `LanguageProvider.tsx`. */
const LANGUAGE_STORAGE_KEY = 'pesticide-advisory-language'

/**
 * The interface language, read without hooks or context.
 *
 * The fallback has to render when the app is broken, and the app owns the i18n
 * provider, so this asks the two places the choice is already recorded: the
 * persisted setting (synchronous, and correct even if the crash happens on the
 * very first render) and then `<html lang>`, which the provider keeps in sync.
 */
function copyForPage() {
  try {
    const saved = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
    if (saved === 'hi') return COPY.hi
    if (saved === 'en' || saved === 'auto') return COPY.en
  } catch {
    // Storage can be unavailable; fall through to the document.
  }
  if (typeof document === 'undefined') return COPY.en
  return document.documentElement.lang.toLowerCase().startsWith('hi') ? COPY.hi : COPY.en
}

/**
 * Development-only diagnostics.
 *
 * The console is a developer tool, not the interface: nothing here reaches the
 * page. In development the full error and React's component stack are logged so
 * the fault can be found. In a production build only the error's name and
 * message are logged — no stack, no file paths — because a browser console is
 * still a place a user can be asked to copy from.
 */
function logRenderError(error: Error, info: ErrorInfo) {
  /* eslint-disable no-console */
  if (import.meta.env.DEV) {
    console.error('[Krishi Salah] render error:', error, info.componentStack)
  } else {
    console.error('[Krishi Salah] render error:', error.name, error.message)
  }
  /* eslint-enable no-console */
}

interface FallbackProps {
  onReload: () => void
}

/** The branded crash screen. Deliberately free of hooks, router and i18n. */
export function ErrorFallback({ onReload }: FallbackProps) {
  const copy = copyForPage()

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="error-fallback"
      className="mx-auto flex max-w-2xl flex-col items-start rounded-card border border-ivory-300 bg-white p-6 shadow-card sm:p-8"
    >
      <span className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-forest-700 text-ivory-50">
          <Icon name="leaf" className="h-[19px] w-[19px]" />
        </span>
        <span className="leading-tight">
          <span className="block font-display text-[15px] font-semibold tracking-tight text-ink-900">
            {copy.brand}
          </span>
          <span className="block text-2xs text-ink-500">{copy.tagline}</span>
        </span>
      </span>

      <span className="mt-6 flex h-10 w-10 items-center justify-center rounded-full bg-gold-100 text-gold-800">
        <Icon name="alert" className="h-5 w-5" />
      </span>

      <h1 className="mt-3 font-display text-[22px] font-semibold leading-snug text-ink-900">
        {copy.title}
      </h1>
      <p className="mt-2 max-w-prose text-sm leading-7 text-ink-700">{copy.body}</p>

      <button
        type="button"
        onClick={onReload}
        className="mt-6 inline-flex min-h-[44px] items-center justify-center gap-2 rounded-field bg-forest-700 px-4 text-sm font-semibold text-white transition-colors duration-150 hover:bg-forest-800 active:bg-forest-900"
      >
        {copy.action}
      </button>
    </div>
  )
}

interface ErrorBoundaryProps {
  children: ReactNode
  /** Rendered instead of the children when they throw. */
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logRenderError(error, info)
  }

  private reload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <ErrorFallback onReload={this.reload} />
    }
    return this.props.children
  }
}
