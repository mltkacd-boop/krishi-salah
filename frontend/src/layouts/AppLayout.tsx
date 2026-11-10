import { Link, Outlet } from 'react-router-dom'

import { BrandMark, BottomNav, DesktopNav } from '../components/Nav'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { useLanguage } from '../i18n/LanguageProvider'

export function AppLayout() {
  const { t } = useLanguage()

  return (
    <div className="flex min-h-screen flex-col bg-ivory-100">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-forest-800 focus:shadow-raised"
      >
        {t('nav.skip')}
      </a>

      <header className="sticky top-0 z-30 border-b border-ivory-300 bg-ivory-100/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-shell items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
          <Link to="/" className="flex-shrink-0 rounded-lg" aria-label={t('brand.name')}>
            <BrandMark />
          </Link>

          <DesktopNav />

          <div className="flex flex-shrink-0 items-center gap-2">
            <LanguageSwitch variant="compact" />
          </div>
        </div>
      </header>

      <main id="main" className="flex-1 pb-24 lg:pb-0">
        <div className="mx-auto max-w-shell px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-12">
          {/* The page renders inside the boundary; the header, footer and
              navigation stay mounted, so a broken page is still a usable site. */}
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>

      <footer className="border-t border-ivory-300 bg-ivory-50">
        <div className="mx-auto max-w-shell px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
          <div className="grid gap-8 md:grid-cols-[1.6fr_1fr]">
            <div>
              <BrandMark />
              <p className="mt-3 max-w-xl text-xs leading-5 text-ink-500">
                {t('footer.disclaimer')}
              </p>
            </div>
            <nav aria-label="Secondary" className="flex flex-col gap-2 md:items-end">
              <Link
                to="/project-info"
                className="text-xs font-medium text-ink-600 underline-offset-4 hover:text-forest-800 hover:underline"
              >
                {t('nav.project')}
              </Link>
              <Link
                to="/safety-guidelines"
                className="text-xs font-medium text-ink-600 underline-offset-4 hover:text-forest-800 hover:underline"
              >
                {t('footer.safetyLink')}
              </Link>
              <Link
                to="/knowledge-base"
                className="text-xs font-medium text-ink-600 underline-offset-4 hover:text-forest-800 hover:underline"
              >
                {t('footer.libraryLink')}
              </Link>
              <Link
                to="/evaluation"
                className="text-xs font-medium text-ink-500 underline-offset-4 hover:text-forest-800 hover:underline"
              >
                {t('footer.evaluation')}
              </Link>
            </nav>
          </div>
          <p className="mt-6 border-t border-ivory-300 pt-4 text-2xs text-ink-500">
            {t('footer.built')}
          </p>
        </div>
      </footer>

      <BottomNav />
    </div>
  )
}
