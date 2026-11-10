import { useId, useMemo, useState } from 'react'

import { Card } from '../components/Card'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { useKnowledgeBase } from '../hooks/useKnowledgeBase'
import { useLanguage } from '../i18n/LanguageProvider'
import type { ApprovedUse, SafetyField, Source } from '../types/api'

/** PHI / REI / PPE, always visible: a record's safety gaps are its headline. */
function SafetyRow({ label, field }: { label: string; field: SafetyField }) {
  const { t } = useLanguage()
  const published = field.status === 'PUBLISHED'
  return (
    <div className="border-b border-ivory-200 py-2 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <dt className="text-xs text-ink-500">{label}</dt>
        <dd className="text-right">
          <span
            className={
              'inline-flex items-center gap-1 text-xs ' +
              (published ? 'font-medium text-ink-800' : 'font-medium text-gold-800')
            }
          >
            <Icon name={published ? 'check' : 'alert'} className="h-3 w-3 flex-shrink-0" />
            {published ? field.value : t('result.notPublished')}
          </span>
        </dd>
      </div>
      {/* Left-aligned: a ragged-left paragraph is measurably harder to read
          than a ragged-right one, and these notes are sentences. */}
      {!published && field.note && (
        <p className="mt-1 text-[11px] leading-4 text-ink-500">{field.note}</p>
      )}
    </div>
  )
}

function RecordCard({ record, cropName, source }: { record: ApprovedUse; cropName: string; source?: Source }) {
  const { t } = useLanguage()
  const actionable = record.advisory_status === 'ACTIONABLE_WITH_EVIDENCE'

  return (
    <Card className="flex flex-col">
      <div className="flex shrink-0 flex-wrap items-start justify-between gap-2 px-5 pt-4">
        <span className="rounded-full bg-sage-200 px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.08em] text-forest-900">
          {cropName}
        </span>
        <span
          className={
            'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-2xs font-semibold ' +
            (actionable ? 'bg-forest-100 text-forest-800' : 'bg-gold-100 text-gold-800')
          }
        >
          <Icon name={actionable ? 'check' : 'info'} className="h-3 w-3" />
          {actionable ? t('kb.actionable') : t('kb.educational')}
        </span>
      </div>

      <div className="shrink-0 px-5 pb-4 pt-3">
        <h3 className="font-display text-[17px] font-semibold leading-snug text-ink-900">
          {record.target_pest_common_name}
        </h3>
        {record.target_pest_scientific_name && (
          <p className="mt-0.5 text-xs italic text-ink-500">{record.target_pest_scientific_name}</p>
        )}
        {record.economic_threshold_level && (
          <p className="mt-2 text-xs text-ink-600">
            <span className="text-ink-500">{t('kb.etl')}: </span>
            {record.economic_threshold_level}
          </p>
        )}
      </div>

      <div className="shrink-0 border-t border-ivory-200 bg-ivory-50 px-5 py-3">
        <p className="label-caps mb-1.5">{t('kb.safety')}</p>
        <dl>
          <SafetyRow label="PHI" field={record.safety_restrictions.phi} />
          <SafetyRow label="REI" field={record.safety_restrictions.rei} />
          <SafetyRow label="PPE" field={record.safety_restrictions.ppe} />
        </dl>
      </div>

      <details className="group shrink-0 border-t border-ivory-200">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-5 py-3 text-xs font-semibold text-ink-800">
          <span>
            {t('kb.interventions')} · {record.interventions.length}
          </span>
          <Icon
            name="chevron-down"
            className="h-4 w-4 flex-shrink-0 text-ink-400 transition-transform group-open:rotate-180"
          />
        </summary>
        <ul className="space-y-2 px-5 pb-4">
          {record.interventions.map((item, index) => (
            <li
              key={`${item.active_ingredient_and_formulation ?? 'item'}-${index}`}
              className="rounded-lg border border-ivory-200 bg-ivory-50 px-3 py-2"
            >
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-500 ring-1 ring-inset ring-ivory-300">
                  {item.control_type}
                </span>
                {item.active_ingredient_and_formulation && (
                  <span className="text-xs font-medium text-ink-800">
                    {item.active_ingredient_and_formulation}
                  </span>
                )}
                {item.dosage && <span className="text-xs text-ink-600">{item.dosage}</span>}
              </div>
              <p className="mt-1 text-[13px] leading-5 text-ink-600">{item.description}</p>
              {item.dosage_unit_note && (
                <p className="mt-1 flex gap-1 text-2xs italic leading-4 text-gold-800">
                  <Icon name="alert" className="mt-0.5 h-3 w-3 flex-shrink-0" />
                  {item.dosage_unit_note}
                </p>
              )}
            </li>
          ))}
        </ul>
      </details>

      <div className="mt-auto border-t border-ivory-200 px-5 py-3 text-2xs leading-4 text-ink-500">
        <p>
          {t('kb.source')}:{' '}
          {source ? (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer noopener"
              className="font-medium text-forest-800 underline-offset-2 hover:underline"
            >
              {source.authority}
            </a>
          ) : (
            record.source_id
          )}
        </p>
        {/* The verification note is long and identical on most records, so it is
            collapsed rather than repeated nine times down the page. */}
        <details className="group mt-1.5">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 font-medium text-ink-600 hover:text-forest-800">
            {t('kb.verifiedBy')}
            <Icon
              name="chevron-down"
              className="h-3 w-3 transition-transform group-open:rotate-180"
            />
          </summary>
          <p className="mt-1 leading-4">{record.verification_note}</p>
        </details>
      </div>
    </Card>
  )
}

export function KnowledgeBase() {
  const { t } = useLanguage()
  const { status, crops, sources, approvedUses, error, refetch } = useKnowledgeBase()
  const [selectedCrop, setSelectedCrop] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const searchId = useId()

  const cropNameById = useMemo(
    () => new Map(crops.map((crop) => [crop.crop_id, crop.crop_name])),
    [crops],
  )
  const sourceById = useMemo(() => new Map(sources.map((s) => [s.source_id, s])), [sources])

  const term = search.trim().toLowerCase()
  const filtered = approvedUses.filter((record) => {
    if (selectedCrop && record.crop_id !== selectedCrop) return false
    if (!term) return true
    const haystack = [
      cropNameById.get(record.crop_id) ?? '',
      record.target_pest_common_name,
      record.target_pest_scientific_name ?? '',
      ...record.interventions.flatMap((item) => [
        item.active_ingredient_and_formulation ?? '',
        item.description,
        item.control_type,
      ]),
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(term)
  })

  return (
    <div>
      <PageHeader eyebrow={t('nav.knowledge')} title={t('kb.title')} description={t('kb.subtitle')} />

      <div className="mb-6 flex items-start gap-3 rounded-panel border border-gold-300 bg-gold-50 px-4 py-4 shadow-card sm:px-5">
        <Icon name="info" className="mt-0.5 h-4 w-4 flex-shrink-0 text-gold-700" />
        <div>
          <p className="text-sm font-semibold text-gold-900">{t('kb.verificationTitle')}</p>
          <p className="mt-1 text-xs leading-5 text-gold-800">{t('kb.verificationBody')}</p>
        </div>
      </div>

      {status === 'loading' && (
        <Card className="p-5">
          <p className="text-sm text-ink-500" role="status">
            {t('kb.loading')}
          </p>
        </Card>
      )}

      {status === 'error' && (
        <Card className="border-danger-200 bg-danger-50 p-5">
          <p className="text-sm font-semibold text-danger-700">{t('kb.error')}</p>
          <p className="mt-1 text-xs text-danger-700">{error}</p>
          <button
            type="button"
            onClick={refetch}
            className="mt-3 inline-flex min-h-[38px] items-center rounded-field border border-danger-300 bg-white px-3.5 text-xs font-semibold text-danger-700 hover:bg-danger-50"
          >
            {t('kb.retry')}
          </button>
        </Card>
      )}

      {status === 'success' && (
        <>
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative w-full lg:max-w-sm">
              <label htmlFor={searchId} className="sr-only">
                {t('kb.searchLabel')}
              </label>
              <Icon
                name="search"
                className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              />
              <input
                id={searchId}
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t('kb.searchPlaceholder')}
                className="min-h-[44px] w-full rounded-field border border-ivory-300 bg-white pl-10 pr-3 text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-forest-500 focus:ring-2 focus:ring-forest-500/15"
              />
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => setSelectedCrop(null)}
                aria-pressed={selectedCrop === null}
                className={
                  'min-h-[34px] rounded-full px-3 text-xs font-medium transition-colors ' +
                  (selectedCrop === null
                    ? 'bg-forest-700 text-white'
                    : 'bg-white text-ink-600 ring-1 ring-inset ring-ivory-300 hover:text-forest-800')
                }
              >
                {t('kb.allCrops')} ({approvedUses.length})
              </button>
              {crops.map((crop) => {
                const count = approvedUses.filter((u) => u.crop_id === crop.crop_id).length
                const active = selectedCrop === crop.crop_id
                return (
                  <button
                    key={crop.crop_id}
                    type="button"
                    onClick={() => setSelectedCrop(crop.crop_id)}
                    aria-pressed={active}
                    className={
                      'min-h-[34px] rounded-full px-3 text-xs font-medium transition-colors ' +
                      (active
                        ? 'bg-forest-700 text-white'
                        : 'bg-white text-ink-600 ring-1 ring-inset ring-ivory-300 hover:text-forest-800')
                    }
                  >
                    {crop.crop_name} ({count})
                  </button>
                )
              })}
            </div>
          </div>

          {filtered.length === 0 ? (
            <Card className="p-8 text-center">
              <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-ivory-100 text-ink-500">
                <Icon name="search" className="h-5 w-5" />
              </span>
              <p className="mt-3 text-sm font-semibold text-ink-900">{t('kb.noResults')}</p>
              <p className="mt-1 text-xs text-ink-500">{t('kb.noResultsBody')}</p>
              <button
                type="button"
                onClick={() => {
                  setSearch('')
                  setSelectedCrop(null)
                }}
                className="mt-4 inline-flex min-h-[38px] items-center rounded-field border border-ivory-300 bg-white px-3.5 text-xs font-semibold text-forest-800 hover:bg-ivory-50"
              >
                {t('kb.clear')}
              </button>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {filtered.map((record) => (
                <RecordCard
                  key={record.approved_use_id}
                  record={record}
                  cropName={cropNameById.get(record.crop_id) ?? record.crop_id}
                  source={sourceById.get(record.source_id)}
                />
              ))}
            </div>
          )}

          <p className="mt-6 text-xs leading-5 text-ink-500">{t('kb.datasetNote')}</p>
        </>
      )}
    </div>
  )
}


