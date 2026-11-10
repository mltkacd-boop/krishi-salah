import { NavLink } from 'react-router-dom'

import { Icon } from './Icon'
import type { IconName } from './Icon'
import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'

interface NavItem {
  to: string
  labelKey: StringKey
  /** Bottom bar only: a label that fits one line at 360px. */
  shortKey?: StringKey
  icon: IconName
}

/** Four destinations. About lives in the footer, not in the primary bar. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', labelKey: 'nav.home', icon: 'home' },
  { to: '/advisory', labelKey: 'nav.advisory', icon: 'chat' },
  { to: '/knowledge-base', labelKey: 'nav.knowledge', shortKey: 'nav.library', icon: 'book' },
  { to: '/safety-guidelines', labelKey: 'nav.safety', icon: 'shield' },
]

export function BrandMark({ compact = false }: { compact?: boolean }) {
  const { t } = useLanguage()
  return (
    <span className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-forest-700 text-ivory-50">
        <Icon name="leaf" className="h-[19px] w-[19px]" />
      </span>
      <span className="leading-tight">
        <span className="block font-display text-[15px] font-semibold tracking-tight text-ink-900">
          {t('brand.name')}
        </span>
        {!compact && (
          <span className="block text-2xs text-ink-500">{t('brand.tagline')}</span>
        )}
      </span>
    </span>
  )
}

/** Desktop navigation: a restrained horizontal bar, not a permanent sidebar. */
export function DesktopNav() {
  const { t } = useLanguage()
  return (
    <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            'rounded-full px-3.5 py-2 text-sm transition-colors ' +
            (isActive
              ? 'bg-forest-50 font-semibold text-forest-900'
              : 'font-medium text-ink-600 hover:bg-ivory-200 hover:text-ink-900')
          }
        >
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  )
}

/**
 * Mobile navigation: fixed to the bottom, where a thumb reaches, with the label
 * always visible under the icon. A drawer hides the four destinations behind a
 * tap; this does not.
 */
export function BottomNav() {
  const { t } = useLanguage()
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-ivory-300 bg-white/95 pb-safe backdrop-blur lg:hidden"
    >
      <ul className="mx-auto grid max-w-md grid-cols-4">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                'relative flex flex-col items-center gap-1 px-1 pb-2 pt-2.5 text-[11px] leading-4 transition-colors ' +
                (isActive ? 'font-semibold text-forest-800' : 'font-medium text-ink-500')
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={
                      'absolute inset-x-4 top-0 h-0.5 rounded-full transition-opacity ' +
                      (isActive ? 'bg-forest-700 opacity-100' : 'opacity-0')
                    }
                  />
                  <Icon name={item.icon} className={'h-[22px] w-[22px] ' + (isActive ? 'text-forest-700' : 'text-ink-400')} />
                  <span className="whitespace-nowrap text-center">
                    {t(item.shortKey ?? item.labelKey)}
                  </span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
