import { useId } from 'react'

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
  const canSubmit = value.trim().length > 0 && !busy

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (canSubmit) onSubmit(value.trim())
      }}
      className="rounded-card border border-ivory-300 bg-white p-4 shadow-raised sm:p-6"
    >
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={inputId} className="label-caps">
          {t('advisory.question')}
        </label>
        <span className="text-2xs tabular-nums text-ink-400">{value.length}/1000</span>
      </div>

      <textarea
        id={inputId}
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
        className="mt-2 w-full resize-y rounded-field border border-ivory-400 bg-ivory-50 px-3.5 py-3 text-[15px] leading-7 text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-forest-500 focus:bg-white"
      />
      <p id={hintId} className="mt-1.5 text-2xs text-ink-500">
        {t('home.composerHint')}
      </p>

      <div className="mt-4 flex flex-col gap-3 border-t border-ivory-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <LanguageSwitch variant="compact" label={t('advisory.language')} />
        <Button type="submit" size="lg" disabled={!canSubmit} className="w-full sm:w-auto">
          <Icon name="search" className="h-[18px] w-[18px]" />
          {busy ? t('advisory.submitting') : t('advisory.submit')}
        </Button>
      </div>

      {showExamples && (
        <div className="mt-4">
          <p className="label-caps mb-2">{t('advisory.examples')}</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_KEYS.map((example) => (
              <button
                key={example.labelKey}
                type="button"
                onClick={() => {
                  onChange(example.query)
                  onSubmit(example.query)
                }}
                className="min-h-[36px] rounded-full border border-ivory-300 bg-ivory-50 px-3 py-1.5 text-xs font-medium text-ink-700 transition-colors hover:border-forest-300 hover:bg-white hover:text-forest-900"
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
