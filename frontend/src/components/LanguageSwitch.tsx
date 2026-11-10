import { useLanguage } from '../i18n/LanguageProvider'

const OPTIONS = [
  { value: 'auto' as const, labelKey: 'advisory.language.auto' as const, short: 'Auto' },
  { value: 'en' as const, labelKey: 'advisory.language.en' as const, short: 'EN' },
  { value: 'hi' as const, labelKey: 'advisory.language.hi' as const, short: 'हिं' },
]

interface LanguageSwitchProps {
  /** `full` shows the word for each option; `compact` shows Auto / EN / हिं. */
  variant?: 'full' | 'compact'
  label?: string
  className?: string
}

/**
 * Three-state language control: follow the question, English, or Hindi.
 *
 * It only affects presentation and the `language` field sent with the next
 * question. It cannot change what the backend decides, and the answer's own
 * language is reported separately on the result.
 */
export function LanguageSwitch({ variant = 'compact', label, className = '' }: LanguageSwitchProps) {
  const { choice, setChoice, t } = useLanguage()

  return (
    <div className={className}>
      {label && <p className="label-caps mb-1.5">{label}</p>}
      <div
        className="inline-flex items-center rounded-full border border-ivory-400 bg-white p-0.5"
        role="group"
        aria-label={label ?? t('advisory.language')}
      >
        {OPTIONS.map((option) => {
          const active = choice === option.value
          const text = variant === 'compact' ? option.short : t(option.labelKey)
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setChoice(option.value)}
              aria-pressed={active}
              title={t(option.labelKey)}
              className={
                'min-h-[34px] rounded-full px-2.5 text-xs transition-colors ' +
                (active
                  ? 'bg-forest-700 font-semibold text-white'
                  : 'font-medium text-ink-500 hover:bg-ivory-100 hover:text-ink-800')
              }
            >
              {text}
            </button>
          )
        })}
      </div>
    </div>
  )
}
