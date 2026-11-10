/**
 * Decision rendering.
 *
 * The badge is the only place the six decision classes become a colour and a
 * sentence. Two properties matter and are asserted for every class:
 *
 * 1. the backend's decision is what is displayed (never derived in the browser)
 * 2. an unknown or absent decision renders as unclassified, not as an approval
 *
 * The second is the one that would be a safety defect: if a future seventh
 * class, or a null, fell through to the ACTIONABLE_RECOMMENDATION styling, the
 * interface would show a green "actionable" card for something the backend
 * never approved.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { LanguageProvider } from '../i18n/LanguageProvider'
import type { AdvisoryDecision } from '../types/api'
import { DecisionBadge } from './DecisionBadge'

const ALL: AdvisoryDecision[] = [
  'ACTIONABLE_RECOMMENDATION',
  'EDUCATIONAL_INFORMATION',
  'SAFETY_REFUSAL',
  'REGULATORY_VERIFICATION_REQUIRED',
  'ESCALATION_REQUIRED',
  'CLARIFICATION_REQUIRED',
]

const EN_LABEL: Record<AdvisoryDecision, string> = {
  ACTIONABLE_RECOMMENDATION: 'Verified recommendation',
  EDUCATIONAL_INFORMATION: 'Educational information only',
  SAFETY_REFUSAL: 'Cannot provide a safe recommendation',
  REGULATORY_VERIFICATION_REQUIRED: 'Product approval needs verification',
  ESCALATION_REQUIRED: 'Consult an agricultural expert',
  CLARIFICATION_REQUIRED: 'More information needed',
}

function renderBadge(decision: AdvisoryDecision | null, outcome = 'answered') {
  return render(
    <LanguageProvider>
      <DecisionBadge decision={decision} outcome={outcome} />
    </LanguageProvider>,
  )
}

describe('DecisionBadge', () => {
  it.each(ALL)('renders %s with its own label and data attribute', (decision) => {
    const { container } = renderBadge(decision)
    expect(screen.getByText(EN_LABEL[decision])).toBeInTheDocument()
    expect(container.querySelector('[data-decision]')).toHaveAttribute('data-decision', decision)
  })

  it('keeps the backend outcome code in the markup, not in the interface', () => {
    const { container } = renderBadge('SAFETY_REFUSAL', 'safety_value_not_published')
    expect(screen.queryByText('safety_value_not_published')).not.toBeInTheDocument()
    expect(container.querySelector('[data-decision]')).toHaveAttribute(
      'data-outcome',
      'safety_value_not_published',
    )
    expect(screen.getByText('Cannot provide a safe recommendation')).toBeInTheDocument()
  })

  it.each(ALL)('never prints the raw class name for %s', (decision) => {
    renderBadge(decision)
    expect(screen.queryByText(decision)).not.toBeInTheDocument()
  })

  it('gives each class a distinct wrapper, so the classes cannot be confused visually', () => {
    const classes = new Set<string>()
    for (const decision of ALL) {
      const { container, unmount } = renderBadge(decision)
      const wrapper = container.querySelector('[data-decision]') as HTMLElement
      classes.add(wrapper.className)
      unmount()
    }
    expect(classes.size).toBe(ALL.length)
  })

  it('renders an unknown decision as unclassified, not as actionable', () => {
    // A class the frontend does not know about: it must degrade to "unclassified".
    const { container } = renderBadge('SOMETHING_NEW' as AdvisoryDecision)
    const wrapper = container.querySelector('[data-decision]') as HTMLElement
    expect(wrapper).toHaveAttribute('data-decision', 'SOMETHING_NEW')
    expect(screen.getByText('Unclassified response')).toBeInTheDocument()
    expect(screen.queryByText(EN_LABEL.ACTIONABLE_RECOMMENDATION)).not.toBeInTheDocument()
    expect(wrapper.className).not.toMatch(/forest-50/)
  })

  it('renders a null decision as unclassified, not as actionable', () => {
    const { container } = renderBadge(null)
    const wrapper = container.querySelector('[data-decision]') as HTMLElement
    expect(wrapper).toHaveAttribute('data-decision', 'NONE')
    expect(screen.getByText('Unclassified response')).toBeInTheDocument()
    expect(wrapper.className).not.toMatch(/forest-50/)
  })

  it('records a crop-level answer for tooling without showing the jargon', () => {
    const { container } = render(
      <LanguageProvider>
        <DecisionBadge decision="EDUCATIONAL_INFORMATION" outcome="answered" scope="crop" />
      </LanguageProvider>,
    )
    expect(container.querySelector('[data-decision]')).toHaveAttribute('data-scope', 'crop')
    expect(screen.queryByText('crop-level')).not.toBeInTheDocument()
  })
})


