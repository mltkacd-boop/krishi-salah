import { Link, Outlet } from 'react-router-dom'

import { BrandMark, BottomNav, DesktopNav } from '../components/Nav'
import { buttonClass } from '../components/Button'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { Icon } from '../components/Icon'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { useLanguage } from '../i18n/LanguageProvider'

/** Footer groups. Kept as data so both languages share one structure. */
const FOOTER_PRIMARY = [
  { to: '/', key: 'nav.home' as const },
  { to: '/advisory', key: 'nav.advisory' as const },
  { to: '/knowledge-base', key: 'nav.knowledge' as const },
  { to: '/safety-guidelines', key: 'nav.safety' as const },
]

const FOOTER_SECONDARY = [
  { to: '/project-info', key: 'nav.project' as const },
  { to: '/evaluation', key: 'footer.evaluation' as const },
]

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

      <header className="sticky top-0 z-30 border-b border-ivory-300/80 bg-ivory-100/85 shadow-header backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-shell items-center justify-between gap-4 px-4 sm:px-6 lg:h-[72px] lg:px-10">
          <Link to="/" className="flex-shrink-0 rounded-lg" aria-label={t('brand.name')}>
            <BrandMark />
          </Link>

          <DesktopNav />

          <div className="flex flex-shrink-0 items-center gap-2">
            <LanguageSwitch variant="compact" />
            <Link
              to="/advisory"
              className={buttonClass('primary', 'md', 'hidden px-4 text-[13px] sm:inline-flex')}
            >
              {t('advisory.submit')}
              <Icon name="arrow-right" className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <main id="main" className="flex-1 pb-24 lg:pb-0">
        <div className="mx-auto max-w-shell px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
          {/* The page renders inside the boundary; the header, footer and
              navigation stay mounted, so a broken page is still a usable site. */}
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>

      <footer className="mt-4 bg-forest-900 text-sage-200">
        <div className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-10 lg:py-14">
          <div className="grid gap-10 lg:grid-cols-[1.35fr_1fr_1fr_1.1fr] lg:gap-12">
            <div>
              <BrandMark tone="dark" />
              <p className="mt-4 max-w-sm text-xs leading-6 text-sage-200">
                {t('footer.disclaimer')}
              </p>
            </div>

            <nav aria-label="Footer" className="flex flex-col gap-2.5">
              <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-sage-400">
                {t('footer.section.ask')}
              </p>
              {FOOTER_PRIMARY.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="w-fit text-xs font-medium text-ivory-50/90 underline-offset-4 transition-colors hover:text-white hover:underline"
                >
                  {t(item.key)}
                </Link>
              ))}
            </nav>

            <nav aria-label="Secondary" className="flex flex-col gap-2.5">
              <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-sage-400">
                {t('footer.section.project')}
              </p>
              {FOOTER_SECONDARY.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="w-fit text-xs font-medium text-ivory-50/90 underline-offset-4 transition-colors hover:text-white hover:underline"
                >
                  {t(item.key)}
                </Link>
              ))}
            </nav>

            <div>
              <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-sage-400">
                {t('footer.section.language')}
              </p>
              <LanguageSwitch variant="full" tone="dark" className="mt-3" />
              <p className="mt-4 text-2xs leading-5 text-sage-300">{t('footer.transparency.title')}</p>
              <p className="mt-1 text-xs leading-5 text-sage-200">{t('footer.transparency.body')}</p>
            </div>
          </div>

          <div className="mt-10 flex flex-col gap-2 border-t border-white/10 pt-5 text-2xs text-sage-300 sm:flex-row sm:items-center sm:justify-between">
            <span>{t('footer.educational')}</span>
            <span>{t('footer.built')}</span>
          </div>
        </div>
      </footer>

      <BottomNav />
    </div>
  )
}
