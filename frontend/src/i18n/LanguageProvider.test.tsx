/**
 * Language switching.
 *
 * Three things are asserted because three of them were wrong or unproven:
 * the chrome actually changes language, the choice survives a reload, and the
 * document's `lang` attribute follows the interface (a Devanagari page that
 * claims `lang="en"` is read aloud in the wrong voice).
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { LanguageSwitch } from '../components/LanguageSwitch'
import { LanguageProvider, useLanguage } from './LanguageProvider'

function Probe() {
  const { lang, choice, t } = useLanguage()
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="choice">{choice}</span>
      <span data-testid="nav-label">{t('nav.advisory')}</span>
      <LanguageSwitch variant="compact" />
    </div>
  )
}

function renderProbe() {
  return render(
    <LanguageProvider>
      <Probe />
    </LanguageProvider>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

describe('LanguageProvider', () => {
  it('starts on "auto" and renders English chrome', () => {
    renderProbe()
    expect(screen.getByTestId('choice')).toHaveTextContent('auto')
    expect(screen.getByTestId('lang')).toHaveTextContent('en')
    expect(screen.getByTestId('nav-label')).toHaveTextContent('Ask assistant')
  })

  it('switches the chrome to Hindi and updates the document language', async () => {
    const user = userEvent.setup()
    renderProbe()
    await user.click(screen.getByRole('button', { name: 'हिं' }))

    expect(screen.getByTestId('lang')).toHaveTextContent('hi')
    expect(screen.getByTestId('nav-label')).toHaveTextContent('सलाह पूछें')
    expect(document.documentElement.lang).toBe('hi')
  })

  it('persists the choice so a returning user does not reselect it', async () => {
    const user = userEvent.setup()
    const { unmount } = renderProbe()
    await user.click(screen.getByRole('button', { name: 'हिं' }))
    expect(window.localStorage.getItem('pesticide-advisory-language')).toBe('hi')
    unmount()

    renderProbe()
    expect(screen.getByTestId('choice')).toHaveTextContent('hi')
    expect(screen.getByTestId('nav-label')).toHaveTextContent('सलाह पूछें')
  })

  it('restores English when the user picks English again', async () => {
    const user = userEvent.setup()
    renderProbe()
    await user.click(screen.getByRole('button', { name: 'हिं' }))
    await user.click(screen.getByRole('button', { name: 'EN' }))

    expect(screen.getByTestId('lang')).toHaveTextContent('en')
    expect(document.documentElement.lang).toBe('en')
    expect(screen.getByTestId('nav-label')).toHaveTextContent('Ask assistant')
  })

  it('marks the active option for assistive technology', async () => {
    const user = userEvent.setup()
    renderProbe()
    const hindi = screen.getByRole('button', { name: 'हिं' })
    expect(hindi).toHaveAttribute('aria-pressed', 'false')
    await user.click(hindi)
    expect(hindi).toHaveAttribute('aria-pressed', 'true')
  })
})

