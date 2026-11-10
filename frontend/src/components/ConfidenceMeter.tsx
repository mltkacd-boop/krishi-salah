import { useLanguage } from '../i18n/LanguageProvider'

interface ConfidenceMeterProps {
  label: 'low' | 'medium' | 'high'
}

const LABEL_TEXT = {
  en: { low: 'Low', medium: 'Medium', high: 'High' },
  hi: { low: 'कम', medium: 'मध्यम', high: 'उच्च' },
}

const BAR = {
  low: 'bg-gold-500',
  medium: 'bg-forest-500',
  high: 'bg-forest-700',
}

/**
 * Qualitative confidence only.
 *
 * The blended score and the two inputs it came from are returned by the backend
 * and shown in the evaluation section of the result; a farmer reading a safety
 * answer gets "Medium", not "0.61". A high score never turns an educational
 * answer into an actionable one, and the UI never re-derives the label.
 */
export function ConfidenceMeter({ label }: ConfidenceMeterProps) {
  const { t, lang } = useLanguage()
  const width = { low: '34%', medium: '67%', high: '100%' }[label]

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="label-caps">{t('result.confidence')}</span>
        <span className="text-xs font-semibold text-ink-800">{LABEL_TEXT[lang][label]}</span>
      </div>
      <div
        className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-ivory-200"
        role="img"
        aria-label={`${t('result.confidence')}: ${LABEL_TEXT[lang][label]}`}
      >
        <div className={`h-full rounded-full ${BAR[label]}`} style={{ width }} />
      </div>
    </div>
  )
}
