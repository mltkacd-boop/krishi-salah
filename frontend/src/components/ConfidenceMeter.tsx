import { useLanguage } from '../i18n/LanguageProvider'
import type { Lang, StringKey } from '../i18n/strings'

interface ConfidenceMeterProps {
  label: 'low' | 'medium' | 'high'
  /**
   * Language to render the meter in. Defaults to the interface language; the
   * result view passes the language the backend answered in, so a Hindi answer
   * is not captioned in English.
   */
  lang?: Lang
}

const BAR = {
  low: 'bg-gold-500',
  medium: 'bg-forest-500',
  high: 'bg-forest-700',
}

const LABEL_KEY: Record<ConfidenceMeterProps['label'], StringKey> = {
  low: 'result.confidence.low',
  medium: 'result.confidence.medium',
  high: 'result.confidence.high',
}

/**
 * Qualitative confidence only.
 *
 * The blended score and the two inputs it came from are returned by the backend
 * and shown in the evaluation section of the result; a farmer reading a safety
 * answer gets "Medium", not "0.61". A high score never turns an educational
 * answer into an actionable one, and the UI never re-derives the label.
 */
export function ConfidenceMeter({ label, lang }: ConfidenceMeterProps) {
  const { t, tFor } = useLanguage()
  const tr = lang ? tFor(lang) : t
  const width = { low: '34%', medium: '67%', high: '100%' }[label]
  // An unknown label falls back to its raw value rather than printing "undefined".
  const labelText = LABEL_KEY[label] ? tr(LABEL_KEY[label]) : String(label)

  return (
    <div>
      {/* Wraps instead of colliding: the caption and the value are two separate
          words in both languages, and at 15rem the pair used to run together.
          The screen-reader-only colon is a real separator in the text, so the
          pair is never read — or copied — as one word ("ConfidenceLow"). */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="label-caps min-w-0">
          {tr('result.confidence')}
          <span className="sr-only">: </span>
        </span>
        <span className="whitespace-nowrap text-xs font-semibold text-ink-800">{labelText}</span>
      </div>
      <div
        className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-ivory-200"
        role="img"
        aria-label={`${tr('result.confidence')}: ${labelText}`}
      >
        <div className={`h-full rounded-full ${BAR[label]}`} style={{ width }} />
      </div>
    </div>
  )
}
