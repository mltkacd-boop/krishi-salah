import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AdvisoryComposer } from '../components/AdvisoryComposer'
import { buttonClass } from '../components/Button'
import { Card, Section } from '../components/Card'
import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { useBackendHealth } from '../hooks/useBackendHealth'
import { useKnowledgeBase } from '../hooks/useKnowledgeBase'
import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'

const TRUST: Array<{ icon: IconName; titleKey: StringKey; bodyKey: StringKey }> = [
  { icon: 'book', titleKey: 'trust.source.title', bodyKey: 'trust.source.body' },
  { icon: 'shield', titleKey: 'trust.rules.title', bodyKey: 'trust.rules.body' },
  { icon: 'user', titleKey: 'trust.escalate.title', bodyKey: 'trust.escalate.body' },
  { icon: 'check', titleKey: 'trust.noGuess.title', bodyKey: 'trust.noGuess.body' },
]

const HELP: StringKey[] = ['home.help1', 'home.help2', 'home.help3', 'home.help4']

const STEPS: Array<{ titleKey: StringKey; bodyKey: StringKey }> = [
  { titleKey: 'home.step1', bodyKey: 'home.step1.body' },
  { titleKey: 'home.step2', bodyKey: 'home.step2.body' },
  { titleKey: 'home.step3', bodyKey: 'home.step3.body' },
  { titleKey: 'home.step4', bodyKey: 'home.step4.body' },
]

export function Home() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const composerRef = useRef<HTMLDivElement | null>(null)

  const health = useBackendHealth()
  const kb = useKnowledgeBase()

  function focusComposer() {
    const section = composerRef.current
    section?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    section?.querySelector('textarea')?.focus({ preventScroll: true })
  }

  function submit(text: string) {
    navigate('/advisory', { state: { query: text } })
  }

  const stats =
    kb.status === 'success'
      ? [
          { value: kb.crops.length, label: t('status.pilotCrops') },
          { value: kb.approvedUses.length, label: t('status.records') },
          { value: kb.sources.length, label: t('status.sources') },
        ]
      : []

  return (
    <div className="space-y-10 sm:space-y-14">
      {/* Hero --------------------------------------------------------------- */}
      <section className="grid items-center gap-8 lg:grid-cols-[1.04fr_0.96fr] lg:gap-14">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-forest-700">
            {t('home.eyebrow')}
          </p>
          <h1 className="mt-3 max-w-[19ch] text-[32px] font-semibold leading-[1.1] tracking-tight text-ink-900 sm:max-w-[22ch] sm:text-[42px] lg:text-[50px]">
            {t('home.title')}
          </h1>
          <p className="mt-4 max-w-xl text-[15px] leading-7 text-ink-600 sm:text-base">
            {t('home.body')}
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <button type="button" onClick={focusComposer} className={buttonClass('primary', 'lg')}>
              {t('home.ctaPrimary')}
              <Icon name="arrow-right" className="h-4 w-4" />
            </button>
            <Link to="/safety-guidelines" className={buttonClass('secondary', 'lg')}>
              {t('home.ctaSecondary')}
            </Link>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-500">
            <span className="inline-flex items-center gap-1.5">
              <span
                className={
                  'h-1.5 w-1.5 rounded-full ' +
                  (health.status === 'error'
                    ? 'bg-danger-500'
                    : health.status === 'success'
                      ? 'bg-forest-600'
                      : 'bg-ink-300')
                }
              />
              {health.status === 'error'
                ? t('status.unreachable')
                : health.status === 'success'
                  ? t('status.live')
                  : t('status.checking')}
            </span>
            {kb.status === 'success' && (
              <span className="tabular-nums">
                {kb.approvedUses.length} {t('status.records')} · {kb.crops.length}{' '}
                {t('status.pilotCrops')}
              </span>
            )}
          </div>
        </div>

        <div className="relative overflow-hidden rounded-card border border-ivory-300 bg-sage-200">
          <img
            src="/hero-cotton.jpg"
            alt=""
            width={1200}
            height={900}
            loading="eager"
            decoding="async"
            /* Capped on tablet so the question box stays near the first screen. */
            className="aspect-[4/3] max-h-[300px] w-full object-cover sm:aspect-[16/9] sm:max-h-[340px] md:max-h-[380px] lg:aspect-[5/4] lg:max-h-none"
          />
          <p className="absolute bottom-2.5 right-3 rounded-full bg-forest-950/45 px-2 py-0.5 text-[10px] text-white/90">
            {t('home.imageCaption')}
          </p>
        </div>
      </section>

      {/* Composer ----------------------------------------------------------- */}
      <section id="ask" ref={composerRef} className="scroll-mt-24">
        <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr] lg:items-start lg:gap-6">
          <AdvisoryComposer
            value={query}
            onChange={setQuery}
            onSubmit={submit}
            tone="home"
          />

          <Card className="p-5 sm:p-6">
            <h2 className="font-display text-[15px] font-semibold text-ink-900">
              {t('home.helpTitle')}
            </h2>
            <ul className="mt-4 space-y-3.5">
              {HELP.map((key) => (
                <li key={key} className="flex gap-3 text-sm leading-6 text-ink-700">
                  <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-forest-50 text-forest-700">
                    <Icon name="check" className="h-3 w-3" />
                  </span>
                  <span>{t(key)}</span>
                </li>
              ))}
            </ul>

            <div className="mt-5 border-t border-ivory-200 pt-4">
              <p className="text-xs leading-5 text-ink-500">{t('home.safetyBody')}</p>
              <Link
                to="/safety-guidelines"
                className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-600"
              >
                {t('home.safetyLink')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
            </div>
          </Card>
        </div>
      </section>

      {/* Trust -------------------------------------------------------------- */}
      <section aria-label={t('home.helpTitle')}>
        <div className="grid overflow-hidden rounded-card border border-ivory-300 bg-white sm:grid-cols-2 lg:grid-cols-4">
          {TRUST.map((item, index) => (
            <div
              key={item.titleKey}
              className={
                'p-5 ' +
                (index > 0 ? 'border-t border-ivory-200 sm:border-t-0 sm:border-l' : '')
              }
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sage-200 text-forest-800">
                <Icon name={item.icon} className="h-[18px] w-[18px]" />
              </span>
              <h3 className="mt-3 text-sm font-semibold text-ink-900">{t(item.titleKey)}</h3>
              <p className="mt-1 text-xs leading-5 text-ink-500">{t(item.bodyKey)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Coverage and workflow ---------------------------------------------- */}
      <section className="grid gap-4 lg:grid-cols-[1fr_1.35fr] lg:gap-6">
        <Card className="p-5 sm:p-6">
          <h2 className="font-display text-[17px] font-semibold text-ink-900">
            {t('home.coverageTitle')}
          </h2>
          <p className="mt-2 text-sm leading-6 text-ink-600">{t('home.coverageBody')}</p>

          {stats.length > 0 ? (
            <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 border-t border-ivory-200 pt-4">
              {stats.map((stat) => (
                <div key={stat.label}>
                  <dd className="font-display text-[26px] font-semibold leading-none tracking-tight text-ink-900 tabular-nums">
                    {stat.value}
                  </dd>
                  <dt className="mt-1.5 text-2xs leading-4 text-ink-500">{stat.label}</dt>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-5 border-t border-ivory-200 pt-4 text-xs text-ink-500">
              {kb.status === 'error' ? t('status.unreachable') : t('status.checking')}
            </p>
          )}

          <Link
            to="/knowledge-base"
            className="mt-5 inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-600"
          >
            {t('nav.knowledge')}
            <Icon name="arrow-right" className="h-3.5 w-3.5" />
          </Link>
        </Card>

        <Card>
          <Section
            title={t('home.stepsTitle')}
            icon={<Icon name="arrow-right" className="h-4 w-4 text-ink-400" />}
          >
            <ol className="space-y-4">
              {STEPS.map((step, index) => (
                <li key={step.titleKey} className="flex gap-3">
                  <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-forest-700 text-2xs font-semibold text-white tabular-nums">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink-900">{t(step.titleKey)}</p>
                    <p className="mt-0.5 text-xs leading-5 text-ink-500">{t(step.bodyKey)}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Section>
        </Card>
      </section>

      {/* Safety emphasis ---------------------------------------------------- */}
      <section className="overflow-hidden rounded-card bg-forest-900 px-6 py-7 sm:px-8 sm:py-9">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between sm:gap-10">
          <div className="max-w-2xl">
            <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-sage-400">
              {t('nav.safety')}
            </p>
            <h2 className="mt-2 font-display text-[22px] font-semibold leading-snug text-ivory-50 sm:text-[26px]">
              {t('home.safetyTitle')}
            </h2>
            <p className="mt-3 text-sm leading-6 text-sage-200">{t('home.safetyBody')}</p>
          </div>
          <Link
            to="/safety-guidelines"
            className="inline-flex min-h-[44px] flex-shrink-0 items-center gap-2 rounded-field border border-sage-400/40 px-4 text-sm font-semibold text-ivory-50 transition-colors hover:bg-forest-800 sm:mt-1"
          >
            {t('home.safetyLink')}
            <Icon name="arrow-right" className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  )
}


