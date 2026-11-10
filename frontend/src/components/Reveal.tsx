import { useEffect, useState } from 'react'
import type { PropsWithChildren } from 'react'

interface RevealProps extends PropsWithChildren {
  className?: string
  /** Stagger, in milliseconds. Kept small: this is a hint, not an animation. */
  delay?: number
}

/**
 * A one-time entrance for a section.
 *
 * It animates on mount rather than on intersection, deliberately. A
 * scroll-triggered reveal leaves hidden content in the document, which
 * disappears from printing, from a full-page screenshot and from any reader
 * whose viewport never intersects it. The motion is a 12px rise with no opacity
 * change, so the text is legible from the first paint, and
 * `prefers-reduced-motion` removes the movement entirely (see index.css).
 */
export function Reveal({ children, className = '', delay = 0 }: RevealProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  return (
    <div
      className={`reveal ${visible ? 'is-visible' : ''} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  )
}
