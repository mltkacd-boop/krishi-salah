import { useId, useRef } from 'react'

import { Button } from './Button'
import { Icon } from './Icon'
import { LanguageSwitch } from './LanguageSwitch'
import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'

/** Examples are real records in the pilot knowledge base — nothing outside it. */
export const EXAMPLE_KEYS: Array<{ query: string; labelKey: StringKey }> = [
  { query: 'How do I control pink bollworm in cotton?', labelKey: 'advisory.example1' },
  { query: 'How do I manage stem borer in rice?', labelKey: 'advisory.example2' },
  { query: 'Aphids on my wheat crop, what should I do?', labelKey: 'advisory.example3' },
  { query: 'Fall armyworm in maize', labelKey: 'advisory.example4' },
  { query: 'How long before harvest after spraying cotton?', labelKey: 'advisory.example5' },
]

/**
 * Crop starters, not a crop field.
 *
 * Picking a crop writes a plain question into the textarea; the request is still
 * exactly what the farmer can see and edit. Nothing is added to the payload, so
 * the backend contract is unchanged and no hidden state can disagree with the
 * visible question.
 */
const CROP_STARTERS: Array<{ id: string; nameKey: StringKey; questionKey: StringKey }> = [
  { id: 'rice', nameKey: 'home.crop.rice', questionKey: 'home.crop.question.rice' },
  { id: 'wheat', nameKey: 'home.crop.wheat', questionKey: 'home.crop.question.wheat' },
  { id: 'maize', nameKey: 'home.crop.maize', questionKey: 'home.crop.question.maize' },
  { id: 'cotton', nameKey: 'home.crop.cotton', questionKey: 'home.crop.question.cotton' },
  { id: 'tomato', nameKey: 'home.crop.tomato', questionKey: 'home.crop.question.tomato' },
]

interface AdvisoryComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (query: string) => void
  busy?: boolean
  invalid?: boolean
  showExamples?: boolean
  /** Grammar: the home page asks a question, the advisory page continues one. */
  tone?: 'home' | 'page'
}

export function AdvisoryComposer({
  value,
  onChange,
  onSubmit,
  busy = false,
  invalid = false,
  showExamples = true,
  tone = 'page',
}: AdvisoryComposerProps) {
  const { t } = useLanguage()
  const inputId = useId()
  const hintId = useId()
  const cropsId = useId()
  const examplesId = useId()
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const canSubmit = value.trim().length > 0 && !busy

  function startWithCrop(questionKey: StringKey) {
    onChange(t(questionKey))
    textareaRef.current?.focus()
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (canSubmit) onSubmit(value.trim())
      }}
      className="rounded-panel border border-ivory-300 bg-white p-4 shadow-raised sm:p-6"
    >
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={inputId} className="label-caps">
          {t('advisory.question')}
        </label>
        <span className="text-2xs tabular-nums text-ink-500">{value.length}/1000</span>
      </div>

      <textarea
        id={inputId}
        ref={textareaRef}
        rows={tone === 'home' ? 3 : 4}
        value={value}
        maxLength={1000}
        aria-describedby={hintId}
        aria-invalid={invalid || undefined}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey) && canSubmit) {
            event.preventDefault()
            onSubmit(value.trim())
          }
        }}
        placeholder={t('advisory.placeholder')}
        className="mt-2 w-full resize-y rounded-field border border-ivory-400 bg-ivory-50 px-3.5 py-3 text-[15px] leading-7 text-ink-900 outline-none transition-colors duration-200 placeholder:text-ink-400 focus:border-forest-500 focus:bg-white focus:ring-2 focus:ring-forest-500/15"
      />
      <p id={hintId} className="mt-1.5 text-2xs text-ink-500">
        {t('home.composerHint')}
      </p>

      {/* Crop starters ---------------------------------------------------- */}
      <div className="mt-4 border-t border-ivory-200 pt-4">
        <p id={cropsId} className="label-caps">
          {t('advisory.crops')}
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-labelledby={cropsId}>
          {CROP_STARTERS.map((crop) => (
            <button
              key={crop.id}
              type="button"
              title={t(crop.questionKey)}
              onClick={() => startWithCrop(crop.questionKey)}
              className="inline-flex min-h-[34px] items-center rounded-full border border-ivory-300 bg-ivory-50 px-3 py-1.5 text-xs font-medium text-ink-700 transition-colors duration-200 hover:border-forest-300 hover:bg-white hover:text-forest-900"
            >
              {t(crop.nameKey)}
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-2xs leading-5 text-ink-500">{t('advisory.cropsHint')}</p>
      </div>

      {/* Language and submit ---------------------------------------------- */}
      <div className="mt-4 flex flex-col gap-3 border-t border-ivory-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <LanguageSwitch variant="compact" label={t('advisory.language')} />
        <Button type="submit" size="lg" disabled={!canSubmit} className="w-full sm:w-auto">
          <Icon
            name={busy ? 'clock' : 'search'}
            className={'h-[18px] w-[18px] ' + (busy ? 'animate-pulse' : '')}
          />
          {busy ? t('advisory.submitting') : t('advisory.submit')}
        </Button>
      </div>

      {showExamples && (
        <div className="mt-4">
          <p id={examplesId} className="label-caps mb-2">
            {t('advisory.examples')}
          </p>
          <div className="flex flex-wrap gap-2" role="group" aria-labelledby={examplesId}>
            {EXAMPLE_KEYS.map((example) => (
              <button
                key={example.labelKey}
                type="button"
                onClick={() => {
                  onChange(example.query)
                  onSubmit(example.query)
                }}
                className="inline-flex min-h-[36px] items-center rounded-full border border-ivory-300 bg-ivory-50 px-3 py-1.5 text-xs font-medium text-ink-700 transition-colors duration-200 hover:border-forest-300 hover:bg-white hover:text-forest-900"
              >
                {t(example.labelKey)}
              </button>
            ))}
          </div>
        </div>
      )}
    </form>
  )
}
