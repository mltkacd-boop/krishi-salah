import { Icon } from './Icon'
import type { IconName } from './Icon'
import { useLanguage } from '../i18n/LanguageProvider'
import type { AdvisoryDecision } from '../types/api'

/**
 * The six decision classes, each with its own treatment.
 *
 * These are the backend's words and the backend's decision. The component picks
 * colour and icon; it never chooses or upgrades a class, and it has no
 * "actionable by default" branch — an unknown value renders as unclassified
 * rather than as an approval.
 *
 * Colour is never the only signal: every class also carries a distinct label,
 * a description and its own icon, so the meaning survives greyscale, colour
 * blindness and a screen reader.
 *
 * The raw class and outcome code are exposed only as `data-*` attributes. They
 * are what a test or an evaluator reads; a farmer reads the sentence.
 */
const STYLES: Record<
  AdvisoryDecision,
  { wrapper: string; chip: string; icon: IconName; iconWrap: string }
> = {
  ACTIONABLE_RECOMMENDATION: {
    wrapper: 'border-forest-300 bg-forest-50',
    chip: 'bg-forest-700 text-white',
    icon: 'check',
    iconWrap: 'bg-forest-700 text-white',
  },
  EDUCATIONAL_INFORMATION: {
    wrapper: 'border-ivory-400 bg-ivory-50',
    chip: 'bg-ink-700 text-white',
    icon: 'book',
    iconWrap: 'bg-ink-700 text-ivory-50',
  },
  SAFETY_REFUSAL: {
    wrapper: 'border-danger-200 bg-danger-50',
    chip: 'bg-danger-600 text-white',
    icon: 'shield',
    iconWrap: 'bg-danger-600 text-white',
  },
  REGULATORY_VERIFICATION_REQUIRED: {
    wrapper: 'border-gold-300 bg-gold-50',
    chip: 'bg-gold-700 text-white',
    icon: 'document',
    iconWrap: 'bg-gold-700 text-white',
  },
  ESCALATION_REQUIRED: {
    wrapper: 'border-ink-400/40 border-l-4 border-l-ink-800 bg-ivory-100',
    chip: 'bg-ink-900 text-ivory-50',
    icon: 'user',
    iconWrap: 'bg-ink-900 text-ivory-50',
  },
  CLARIFICATION_REQUIRED: {
    wrapper: 'border-dashed border-ink-400 bg-white',
    chip: 'bg-white text-ink-800 ring-1 ring-inset ring-ink-400/50',
    icon: 'info',
    iconWrap: 'bg-ivory-200 text-ink-800',
  },
}

interface DecisionBadgeProps {
  decision: AdvisoryDecision | null
  outcome: string
  scope?: 'record' | 'crop'
}

export function DecisionBadge({ decision, outcome, scope }: DecisionBadgeProps) {
  const { t } = useLanguage()
  // A class this build does not know is treated exactly like no class at all:
  // it keeps the backend's value in `data-decision`, but it must not borrow
  // another class's wording. Without this check `t()` returns the raw key
  // ("decision.SOMETHING_NEW") and the badge would print an i18n key at a user.
  const known = decision !== null && decision in STYLES
  const style = known ? STYLES[decision] : null
  const title = known ? t(`decision.${decision}`) : t('decision.unknown')
  const description = known ? t(`decision.${decision}.desc`) : ''

  return (
    <div
      className={
        'flex scroll-mt-20 items-start gap-3 rounded-card border p-4 sm:gap-4 sm:p-5 ' +
        (style?.wrapper ?? 'border-ivory-400 bg-white')
      }
      role="status"
      data-decision={decision ?? 'NONE'}
      data-outcome={outcome}
      data-scope={scope ?? 'record'}
    >
      <span
        className={
          'flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full sm:h-10 sm:w-10 ' +
          (style?.iconWrap ?? 'bg-ivory-200 text-ink-700')
        }
      >
        <Icon name={style?.icon ?? 'info'} className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
          {/* Sentence case, not caps: these are long friendly phrases and
              uppercase makes them read as a system code. */}
          <span
            className={
              'rounded-full px-2.5 py-1 text-xs font-semibold ' +
              (style?.chip ?? 'bg-ivory-200 text-ink-700')
            }
          >
            {title}
          </span>
        </div>
        {description && (
          <p className="mt-2 text-sm leading-6 text-ink-700">{description}</p>
        )}
      </div>
    </div>
  )
}
