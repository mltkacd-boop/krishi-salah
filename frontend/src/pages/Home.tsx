import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AdvisoryComposer } from '../components/AdvisoryComposer'
import { buttonClass } from '../components/Button'
import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { Reveal } from '../components/Reveal'
import { useBackendHealth } from '../hooks/useBackendHealth'
import { useKnowledgeBase } from '../hooks/useKnowledgeBase'
import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'

/** The five crops the pilot covers, in the order the brief lists them. */
const CROPS: Array<{ id: string; nameKey: StringKey; questionKey: StringKey }> = [
  { id: 'rice', nameKey: 'home.crop.rice', questionKey: 'home.crop.question.rice' },
  { id: 'wheat', nameKey: 'home.crop.wheat', questionKey: 'home.crop.question.wheat' },
  { id: 'maize', nameKey: 'home.crop.maize', questionKey: 'home.crop.question.maize' },
  { id: 'cotton', nameKey: 'home.crop.cotton', questionKey: 'home.crop.question.cotton' },
  { id: 'tomato', nameKey: 'home.crop.tomato', questionKey: 'home.crop.question.tomato' },
]

const STEPS: Array<{ titleKey: StringKey; bodyKey: StringKey; icon: IconName }> = [
  { titleKey: 'home.how.1.title', bodyKey: 'home.how.1.body', icon: 'sprout' },
  { titleKey: 'home.how.2.title', bodyKey: 'home.how.2.body', icon: 'search' },
  { titleKey: 'home.how.3.title', bodyKey: 'home.how.3.body', icon: 'book' },
]

const HELP: StringKey[] = ['home.help1', 'home.help2', 'home.help3', 'home.help4']

const LEARNING: Array<{ icon: IconName; titleKey: StringKey; bodyKey: StringKey }> = [
  { icon: 'shield', titleKey: 'home.learn.protection.title', bodyKey: 'home.learn.protection.body' },
  { icon: 'search', titleKey: 'home.learn.identify.title', bodyKey: 'home.learn.identify.body' },
  { icon: 'book', titleKey: 'home.learn.knowledge.title', bodyKey: 'home.learn.knowledge.body' },
  { icon: 'alert', titleKey: 'home.learn.safety.title', bodyKey: 'home.learn.safety.body' },
]

const TRUST_POINTS: StringKey[] = ['home.trust.1', 'home.trust.2', 'home.trust.3']
const LIMITS: StringKey[] = ['about.limit1', 'about.limit2', 'about.limit3', 'about.limit4']

/** Section heading: one shape, used four times, so the page reads as one page. */
function SectionHeading({
  id,
  eyebrow,
  title,
  subtitle,
  action,
}: {
  id: string
  eyebrow: string
  title: string
  subtitle?: string
  action?: React.ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <p className="label-caps">{eyebrow}</p>
        <h2 id={id} className="mt-2 text-section font-semibold tracking-[-0.02em] text-forest-900">
          {title}
        </h2>
        {subtitle && <p className="mt-2 text-sm leading-6 text-ink-600 sm:text-[15px]">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Home() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const composerRef = useRef<HTMLDivElement | null>(null)

  const health = useBackendHealth()
  const kb = useKnowledgeBase()
  const kbReady = kb.status === 'success'

  function focusComposer() {
    const section = composerRef.current
    section?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    section?.querySelector('textarea')?.focus({ preventScroll: true })
  }

  function submit(text: string) {
    navigate('/advisory', { state: { query: text } })
  }

  /** Records per crop, read from the loaded knowledge base — never hardcoded. */
  function recordsFor(id: string) {
    const crop = kb.crops.find(
      (item) => item.crop_id.toLowerCase() === id || item.crop_name.toLowerCase() === id,
    )
    if (!crop) return null
    return kb.approvedUses.filter((record) => record.crop_id === crop.crop_id).length
  }

  const counts = kbReady
    ? [
        { value: kb.crops.length, labelKey: 'status.pilotCrops' as StringKey },
        { value: kb.approvedUses.length, labelKey: 'status.records' as StringKey },
        { value: kb.sources.length, labelKey: 'status.sources' as StringKey },
      ]
    : []

  return (
    <div>
      {/* Hero ---------------------------------------------------------------- */}
      <section className="-mx-4 -mt-6 bg-ivory-wash sm:-mx-6 sm:-mt-8 lg:-mx-10 lg:-mt-10">
        <div className="mx-auto max-w-shell px-4 pb-20 pt-10 sm:px-6 sm:pb-24 sm:pt-14 lg:px-10 lg:pb-24 lg:pt-16">
          <div className="grid items-center gap-10 lg:grid-cols-[1.02fr_0.98fr] lg:gap-14">
            <div className="animate-fade-up">
              <p className="inline-flex items-center gap-2 rounded-full border border-sage-300 bg-white/70 px-3 py-1 text-2xs font-semibold uppercase tracking-[0.16em] text-forest-700">
                <span className="h-1.5 w-1.5 rounded-full bg-gold-400" aria-hidden="true" />
                {t('home.eyebrow')}
              </p>

              <h1 className="mt-5 max-w-[21ch] text-hero font-semibold tracking-[-0.028em] text-forest-900">
                {t('home.title')}
              </h1>

              <p className="mt-5 max-w-[54ch] text-[15px] leading-7 text-ink-600 sm:text-[17px] sm:leading-8">
                {t('home.body')}
              </p>

              <div className="mt-7 flex flex-col gap-2.5 sm:flex-row sm:items-center sm:gap-3">
                <button type="button" onClick={focusComposer} className={buttonClass('primary', 'lg')}>
                  {t('home.ctaPrimary')}
                  <Icon name="arrow-right" className="h-4 w-4" />
                </button>
                <Link to="/knowledge-base" className={buttonClass('secondary', 'lg')}>
                  <Icon name="book" className="h-4 w-4 text-forest-700" />
                  {t('home.ctaSecondary')}
                </Link>
              </div>

              <p className="mt-5 flex items-start gap-2 text-2xs leading-5 text-ink-500">
                <Icon name="shield" className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-forest-600" />
                {t('home.hero.note')}
              </p>

              <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-ivory-300 pt-4 text-2xs text-ink-500">
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
                {counts.length > 0 && (
                  <span className="tabular-nums">
                    {counts.map((count, index) => (
                      <span key={count.labelKey}>
                        {index > 0 && <span className="px-1.5 text-ivory-400">·</span>}
                        {count.value} {t(count.labelKey)}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            </div>

            <div className="relative animate-fade-in">
              <div className="overflow-hidden rounded-panel border border-ivory-300 bg-sage-200 shadow-lift">
                <img
                  src="/hero-cotton.jpg"
                  alt=""
                  width={1200}
                  height={900}
                  loading="eager"
                  decoding="async"
                  /* Capped on tablet so the question box stays near the first screen. */
                  className="aspect-[4/3] max-h-[320px] w-full object-cover sm:aspect-[16/10] sm:max-h-[360px] md:max-h-[400px] lg:aspect-[5/4] lg:max-h-none"
                />
              </div>

              <div className="absolute inset-x-3 bottom-3 flex items-center gap-2 rounded-card border border-white/40 bg-forest-950/55 px-3 py-2 backdrop-blur-sm sm:inset-x-4 sm:bottom-4">
                <Icon name="leaf" className="h-4 w-4 flex-shrink-0 text-sage-300" />
                <p className="min-w-0 text-2xs leading-4 text-ivory-50/95">{t('home.imageCaption')}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Composer, lifted over the hero edge --------------------------------- */}
      <section id="ask" ref={composerRef} className="relative z-10 -mt-20 scroll-mt-24 sm:-mt-24">
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr] lg:items-start lg:gap-5">
          <AdvisoryComposer value={query} onChange={setQuery} onSubmit={submit} tone="home" />

          <aside className="rounded-card border border-sage-300 bg-sage-50 p-5 shadow-card sm:p-6">
            <h2 className="font-display text-[15px] font-semibold text-forest-900">
              {t('home.helpTitle')}
            </h2>
            <ul className="mt-4 space-y-3.5">
              {HELP.map((key) => (
                <li key={key} className="flex gap-2.5 text-sm leading-6 text-ink-700">
                  <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-white text-forest-700 ring-1 ring-inset ring-sage-300">
                    <Icon name="check" className="h-3 w-3" />
                  </span>
                  <span>{t(key)}</span>
                </li>
              ))}
            </ul>
            <div className="mt-5 border-t border-sage-200 pt-4">
              <p className="text-xs leading-5 text-ink-600">{t('home.safetyBody')}</p>
              <Link
                to="/safety-guidelines"
                className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-600"
              >
                {t('home.safetyLink')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
            </div>
          </aside>
        </div>
      </section>

      {/* A. How Krishi Salah works ------------------------------------------- */}
      <section aria-labelledby="how-it-works" className="mt-12 sm:mt-16 lg:mt-24">
        <Reveal>
          <SectionHeading
            id="how-it-works"
            eyebrow={t('home.how.eyebrow')}
            title={t('home.how.title')}
            subtitle={t('home.how.subtitle')}
          />
        </Reveal>

        <ol className="relative grid gap-3 sm:gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.titleKey} className="relative">
              <Reveal delay={index * 90} className="h-full">
                <div className="group h-full rounded-card border border-ivory-300 bg-white p-5 shadow-card transition-[box-shadow,border-color] duration-300 hover:border-sage-300 hover:shadow-raised sm:p-6">
                  <div className="flex items-center justify-between">
                    <span className="font-display text-[32px] font-semibold leading-none tracking-[-0.04em] text-sage-500 tabular-nums">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-forest-50 text-forest-700 ring-1 ring-inset ring-forest-100">
                      <Icon name={step.icon} className="h-[19px] w-[19px]" />
                    </span>
                  </div>
                  <h3 className="mt-5 font-display text-[16px] font-semibold text-ink-900">
                    {t(step.titleKey)}
                  </h3>
                  <p className="mt-1.5 text-sm leading-6 text-ink-600">{t(step.bodyKey)}</p>
                </div>
              </Reveal>
              {index < STEPS.length - 1 && (
                <span
                  aria-hidden="true"
                  className="absolute -right-2.5 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full border border-ivory-300 bg-white text-ink-400 md:flex"
                >
                  <Icon name="arrow-right" className="h-3 w-3" />
                </span>
              )}
            </li>
          ))}
        </ol>
      </section>

      {/* B. Supported crops --------------------------------------------------- */}
      <section aria-labelledby="supported-crops" className="mt-12 sm:mt-16 lg:mt-24">
        <Reveal>
          <SectionHeading
            id="supported-crops"
            eyebrow={t('home.crops.eyebrow')}
            title={t('home.crops.title')}
            subtitle={t('home.crops.subtitle')}
            action={
              <Link
                to="/knowledge-base"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-600"
              >
                {t('home.crops.cta')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
            }
          />
        </Reveal>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-5">
          {CROPS.map((crop, index) => {
            const records = recordsFor(crop.id)
            return (
              <Reveal key={crop.id} delay={index * 70} className="h-full">
                <Link
                  to="/advisory"
                  state={{ query: t(crop.questionKey) }}
                  className="group flex h-full flex-col overflow-hidden rounded-card border border-ivory-300 bg-white shadow-card transition-[transform,box-shadow,border-color] duration-300 ease-out hover:-translate-y-1 hover:border-sage-300 hover:shadow-lift motion-reduce:transform-none"
                >
                  <span className="relative block overflow-hidden bg-sage-200">
                    <img
                      src={`/crops/${crop.id}.jpg`}
                      alt=""
                      width={900}
                      height={600}
                      loading="eager"
                      decoding="async"
                      className="aspect-[4/3] w-full object-cover transition-transform duration-500 ease-out group-hover:scale-[1.04] motion-reduce:transform-none"
                    />
                  </span>
                  <span className="flex flex-1 flex-col p-3.5">
                    <span className="font-display text-[15px] font-semibold text-ink-900">
                      {t(crop.nameKey)}
                    </span>
                    <span className="mt-0.5 text-2xs leading-4 text-ink-500">
                      {records === null
                        ? t('status.checking')
                        : records > 0
                          ? `${records} ${records === 1 ? t('home.crops.recordOne') : t('home.crops.records')}`
                          : t('home.crop.pilot')}
                    </span>
                    <span className="mt-auto inline-flex items-center gap-1 pt-3 text-2xs font-semibold text-forest-800">
                      {t('home.crop.cta')}
                      <Icon
                        name="arrow-right"
                        className="h-3 w-3 transition-transform duration-300 group-hover:translate-x-0.5"
                      />
                    </span>
                  </span>
                </Link>
              </Reveal>
            )
          })}
        </div>
        <p className="mt-3 text-2xs text-ink-500">{t('home.crops.imageNote')}</p>
      </section>

      {/* C. Knowledge and learning ------------------------------------------- */}
      <section aria-labelledby="knowledge-and-learning" className="mt-12 sm:mt-16 lg:mt-24">
        <Reveal>
          <SectionHeading
            id="knowledge-and-learning"
            eyebrow={t('home.learn.eyebrow')}
            title={t('home.learn.title')}
            subtitle={t('home.learn.subtitle')}
          />
        </Reveal>

        <div className="grid gap-3 sm:gap-4 md:grid-cols-2">
          {LEARNING.map((item, index) => (
            <Reveal key={item.titleKey} delay={index * 70} className="h-full">
              <article className="group flex h-full gap-4 rounded-card border border-ivory-300 bg-white p-5 shadow-card transition-[box-shadow,border-color] duration-300 hover:border-sage-300 hover:shadow-raised sm:p-6">
                <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-sage-100 text-forest-800 ring-1 ring-inset ring-sage-300">
                  <Icon name={item.icon} className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <h3 className="font-display text-[15px] font-semibold leading-snug text-ink-900">
                    {t(item.titleKey)}
                  </h3>
                  <p className="mt-1.5 text-sm leading-6 text-ink-600">{t(item.bodyKey)}</p>
                </div>
              </article>
            </Reveal>
          ))}
        </div>

        <Reveal delay={80}>
          <div className="mt-3 grid overflow-hidden rounded-card border border-ivory-300 bg-white shadow-card sm:mt-4 sm:grid-cols-[1fr_0.85fr]">
            <div className="p-5 sm:p-6">
              <p className="label-caps">{t('home.learn.cta')}</p>
              <h3 className="mt-2 font-display text-[19px] font-semibold tracking-[-0.01em] text-forest-900">
                {t('home.coverageTitle')}
              </h3>
              <p className="mt-2 max-w-md text-sm leading-6 text-ink-600">{t('home.coverageBody')}</p>

              {counts.length > 0 ? (
                <dl className="mt-5 grid grid-cols-3 gap-4 border-t border-ivory-200 pt-4">
                  {counts.map((count) => (
                    <div key={count.labelKey}>
                      <dd className="font-display text-[24px] font-semibold leading-none tracking-tight text-forest-900 tabular-nums">
                        {count.value}
                      </dd>
                      <dt className="mt-1.5 text-2xs leading-4 text-ink-500">{t(count.labelKey)}</dt>
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
                {t('home.learn.cta')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="relative hidden min-h-[15rem] sm:block">
              {/* Absolute so the photograph fills the panel without deciding its height. */}
              <img
                src="/crops/wheat.jpg"
                alt=""
                loading="lazy"
                decoding="async"
                className="absolute inset-0 h-full w-full object-cover"
              />
              <span
                className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent"
                aria-hidden="true"
              />
            </div>
          </div>
        </Reveal>
      </section>

      {/* D. Safety and trust --------------------------------------------------- */}
      <section aria-label={t('home.trust.title')} className="mt-12 grid gap-3 sm:mt-16 sm:gap-4 lg:mt-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
        <Reveal className="h-full">
          <div className="h-full overflow-hidden rounded-panel bg-forest-depth px-6 py-8 text-ivory-50 shadow-raised sm:px-8 sm:py-10">
            <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-sage-400">
              {t('home.trust.title')}
            </p>
            <h2 className="mt-2.5 font-display text-[24px] font-semibold leading-tight tracking-[-0.02em] text-ivory-50 sm:text-[28px]">
              {t('home.safetyTitle')}
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-sage-200 sm:text-[15px]">
              {t('home.trust.body')}
            </p>

            <ul className="mt-6 space-y-3">
              {TRUST_POINTS.map((key) => (
                <li key={key} className="flex gap-2.5 text-sm leading-6 text-ivory-50/95">
                  <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-white/10 text-sage-300 ring-1 ring-inset ring-sage-400/35">
                    <Icon name="check" className="h-3 w-3" />
                  </span>
                  <span>{t(key)}</span>
                </li>
              ))}
            </ul>

            <Link
              to="/safety-guidelines"
              className={buttonClass('onDark', 'md', 'mt-7 w-full sm:w-auto')}
            >
              {t('home.safetyLink')}
              <Icon name="arrow-right" className="h-4 w-4" />
            </Link>
          </div>
        </Reveal>

        <Reveal delay={90} className="h-full">
          <div className="h-full rounded-panel border border-ivory-300 bg-white p-6 shadow-card sm:p-7">
            <h2 className="font-display text-[17px] font-semibold text-ink-900">
              {t('home.trust.limits')}
            </h2>
            <ol className="mt-4 space-y-3.5">
              {LIMITS.map((key, index) => (
                <li key={key} className="flex gap-3 text-xs leading-5 text-ink-600">
                  <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-ivory-100 text-2xs font-semibold text-ink-600 tabular-nums">
                    {index + 1}
                  </span>
                  <span>{t(key)}</span>
                </li>
              ))}
            </ol>
            <p className="mt-5 border-t border-ivory-200 pt-4 text-2xs leading-5 text-ink-500">
              {t('home.dataset.note')}
            </p>
          </div>
        </Reveal>
      </section>
    </div>
  )
}
