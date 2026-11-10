import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'

import { STRINGS } from './strings'
import type { Lang, StringKey } from './strings'

type LanguageChoice = Lang | 'auto'

type Translate = (key: StringKey) => string

interface LanguageContextValue {
  /** Language the interface is rendered in. */
  lang: Lang
  /** What the user picked: an explicit language, or "follow my question". */
  choice: LanguageChoice
  setChoice: (choice: LanguageChoice) => void
  t: Translate
  /**
   * The same translator bound to another language.
   *
   * Used by the result view, which must follow `response.answer_language` rather
   * than the interface chrome: with the swipe set to "follow my question", a
   * Hindi answer is rendered under English headings otherwise, so a farmer reads
   * a Hindi refusal framed by English labels. One string table, two callers.
   */
  tFor: (lang: Lang) => Translate
}

const STORAGE_KEY = 'pesticide-advisory-language'
const LanguageContext = createContext<LanguageContextValue | null>(null)

function initialChoice(): LanguageChoice {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'en' || saved === 'hi' || saved === 'auto') return saved
  } catch {
    // storage can be unavailable (private mode); fall through to the default
  }
  return 'auto'
}

/**
 * Interface language.
 *
 * `auto` renders English chrome and lets the backend answer in the language of
 * the question; picking हिंदी switches both. The choice is persisted because a
 * farmer returning to the page should not have to reselect it, and it is the
 * only frontend state that is remembered.
 */
export function LanguageProvider({ children }: PropsWithChildren) {
  const [choice, setChoiceState] = useState<LanguageChoice>(initialChoice)

  const setChoice = useCallback((next: LanguageChoice) => {
    setChoiceState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // non-fatal: the session still uses the chosen language
    }
  }, [])

  const lang: Lang = choice === 'hi' ? 'hi' : 'en'

  // index.html ships lang="en"; without this the document claims to be English
  // while the page is Devanagari, so screen readers pick the wrong voice and
  // the browser offers to translate a page it can already read.
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const value = useMemo<LanguageContextValue>(() => {
    const tFor = (target: Lang): Translate => (key) =>
      STRINGS[target][key] ?? STRINGS.en[key] ?? key
    return {
      lang,
      choice,
      setChoice,
      t: tFor(lang),
      tFor,
    }
  }, [lang, choice, setChoice])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside LanguageProvider')
  return ctx
}
