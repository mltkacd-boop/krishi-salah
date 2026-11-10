import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Card } from '../components/Card'
import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'
import { advisoryService } from '../services/advisoryService'
import type { RulesStatusResponse } from '../types/api'

const TERMS: Array<{ icon: IconName; titleKey: StringKey; bodyKey: StringKey }> = [
  { icon: 'clock', titleKey: 'safety.phi.title', bodyKey: 'safety.phi.body' },
  { icon: 'user', titleKey: 'safety.rei.title', bodyKey: 'safety.rei.body' },
  { icon: 'shield', titleKey: 'safety.ppe.title', bodyKey: 'safety.ppe.body' },
  { icon: 'document', titleKey: 'safety.label.title', bodyKey: 'safety.label.body' },
  { icon: 'check', titleKey: 'safety.registry.title', bodyKey: 'safety.registry.body' },
]

/**
 * Plain-language safety page.
 *
 * Rule identifiers, severities, precedence and thresholds used to live here;
 * they are engineering detail, not a farmer's vocabulary, and they are now on
 * the evaluation page. What stays is the information a person needs before
 * spraying, and the honest statement of how many records are actionable.
 */
export function SafetyGuidelines() {
  const { t } = useLanguage()
  const [data, setData] = useState<RulesStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    advisoryService
      .rulesStatus()
      .then((result) => !cancelled && setData(result))
      .catch((err: Error) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={t('nav.safety')} title={t('safety.title')} description={t('safety.subtitle')} />

      <section>
        <h2 className="text-section font-semibold tracking-[-0.02em] text-forest-900">{t('safety.termsTitle')}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-3">
          {TERMS.map((term) => (
            <Card key={term.titleKey} className="p-5 transition-[box-shadow,border-color] duration-300 hover:border-sage-300 hover:shadow-raised sm:p-6">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-sage-100 text-forest-800 ring-1 ring-inset ring-sage-300">
                <Icon name={term.icon} className="h-[18px] w-[18px]" />
              </span>
              <h3 className="mt-4 font-display text-[15px] font-semibold leading-snug text-ink-900">
                {t(term.titleKey)}
              </h3>
              <p className="mt-1.5 text-sm leading-6 text-ink-600">{t(term.bodyKey)}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="rounded-panel border border-gold-300 bg-gold-50 px-5 py-5 shadow-card sm:px-7 sm:py-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gold-200 text-gold-900">
            <Icon name="alert" className="h-[18px] w-[18px]" />
          </span>
          <div>
            <h2 className="font-display text-[15px] font-semibold text-gold-900">
              {t('safety.gateTitle')}
            </h2>
            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-gold-800">{t('safety.gateBody')}</p>
            <Link
              to="/knowledge-base"
              className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-gold-900 underline-offset-4 hover:underline"
            >
              {t('nav.knowledge')}
              <Icon name="arrow-right" className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {error && (
        <Card className="border-danger-200 bg-danger-50 p-4 text-xs text-danger-700">
          {t('safety.error')}: {error}
        </Card>
      )}

      {!data && !error && (
        <Card className="p-5 text-sm text-ink-500">
          <span role="status">{t('safety.loading')}</span>
        </Card>
      )}

      {data && (
        <Card className="border-forest-200 bg-forest-50">
          <div className="flex items-start gap-3 p-5 sm:p-6">
            <span className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-forest-700 text-white">
              <Icon name="info" className="h-[18px] w-[18px]" />
            </span>
            <div>
              <h2 className="font-display text-[15px] font-semibold text-forest-900">
                {data.knowledge_base.actionable_with_evidence} / {data.knowledge_base.records}{' '}
                {t('safety.headline')}
              </h2>
              {/* The backend's own words, kept verbatim and labelled as such. */}
              <p className="mt-1 text-2xs text-forest-700">{t('safety.backendReason')}</p>
              <p className="mt-1 text-xs leading-5 text-forest-800">{data.knowledge_base.reason}</p>
              <Link
                to="/evaluation"
                className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-forest-900 underline-offset-4 hover:underline"
              >
                {t('footer.evaluation')}
                <Icon name="arrow-right" className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
