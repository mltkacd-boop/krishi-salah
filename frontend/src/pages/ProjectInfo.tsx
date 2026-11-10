import { Link } from 'react-router-dom'

import { Card, Section } from '../components/Card'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { useKnowledgeBase } from '../hooks/useKnowledgeBase'
import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'

const STEPS: StringKey[] = ['home.step1', 'home.step2', 'home.step3', 'home.step4']
const STEP_BODIES: StringKey[] = [
  'home.step1.body',
  'home.step2.body',
  'home.step3.body',
  'home.step4.body',
]
const LIMITS: StringKey[] = ['about.limit1', 'about.limit2', 'about.limit3', 'about.limit4']

/**
 * Public-facing About. No registration number, no submission metadata: those are
 * in the evaluation view, where a person marking the project looks for them.
 */
export function ProjectInfo() {
  const { t } = useLanguage()
  const kb = useKnowledgeBase()

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t('about.eyebrow')} title={t('about.title')} description={t('about.subtitle')} />

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <Section
            title={t('about.whatTitle')}
            icon={<Icon name="leaf" className="h-4 w-4 text-ink-400" />}
          >
            <p className="max-w-2xl text-sm leading-7 text-ink-700">{t('about.whatBody')}</p>
          </Section>
        </Card>

        <Card>
          <Section
            title={t('about.coverageTitle')}
            icon={<Icon name="sprout" className="h-4 w-4 text-ink-400" />}
          >
            <p className="text-sm leading-6 text-ink-600">{t('about.coverageBody')}</p>

            <p className="label-caps mt-4">{t('about.cropsLabel')}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {kb.status === 'success' ? (
                kb.crops.map((crop) => (
                  <span
                    key={crop.crop_id}
                    className="rounded-full bg-sage-200 px-2.5 py-1 text-xs font-medium text-forest-900"
                  >
                    {crop.crop_name}
                  </span>
                ))
              ) : (
                <span className="text-xs text-ink-500">
                  {kb.status === 'error'
                    ? t('status.unreachable')
                    : t('status.checking')}
                </span>
              )}
            </div>

            {kb.status === 'success' && (
              <p className="mt-3 text-xs tabular-nums text-ink-500">
                {kb.approvedUses.length} {t('status.records')} · {kb.sources.length}{' '}
                {t('status.sources')}
              </p>
            )}
          </Section>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <Section
            title={t('about.languageTitle')}
            icon={<Icon name="globe" className="h-4 w-4 text-ink-400" />}
          >
            <p className="text-sm leading-6 text-ink-600">{t('about.languageBody')}</p>
          </Section>
        </Card>

        <Card>
          <Section
            title={t('about.showTitle')}
            icon={<Icon name="shield" className="h-4 w-4 text-ink-400" />}
          >
            <p className="text-sm leading-6 text-ink-600">{t('about.showBody')}</p>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
              <Link
                to="/safety-guidelines"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-600"
              >
                {t('nav.safety')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
              <Link
                to="/knowledge-base"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-forest-800 hover:text-forest-600"
              >
                {t('nav.knowledge')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
            </div>
          </Section>
        </Card>
      </div>

      <Card>
        <Section
          title={t('about.processTitle')}
          icon={<Icon name="arrow-right" className="h-4 w-4 text-ink-400" />}
        >
          <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {STEPS.map((key, index) => (
              <li key={key} className="flex gap-3">
                <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-forest-700 text-2xs font-semibold tabular-nums text-white">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink-900">{t(key)}</p>
                  <p className="mt-0.5 text-xs leading-5 text-ink-500">{t(STEP_BODIES[index])}</p>
                </div>
              </li>
            ))}
          </ol>
        </Section>
      </Card>

      <Card className="border-gold-300 bg-gold-50">
        <div className="p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gold-100 text-gold-800">
              <Icon name="alert" className="h-[18px] w-[18px]" />
            </span>
            <div className="min-w-0">
              <h2 className="font-display text-[15px] font-semibold text-gold-900">
                {t('about.limitsTitle')}
              </h2>
              <ul className="mt-2 max-w-3xl space-y-1.5">
                {LIMITS.map((key) => (
                  <li key={key} className="flex gap-2 text-xs leading-5 text-gold-800">
                    <span className="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-gold-700" />
                    <span>{t(key)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Card>

      <p className="border-t border-ivory-300 pt-4 text-2xs leading-5 text-ink-500">
        {t('about.titleLine')} ·{' '}
        <Link to="/evaluation" className="underline-offset-4 hover:text-forest-800 hover:underline">
          {t('footer.evaluation')}
        </Link>
      </p>
    </div>
  )
}
