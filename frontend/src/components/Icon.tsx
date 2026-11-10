import type { SVGProps } from 'react'

/**
 * Inline icon set.
 *
 * Hand-drawn 24×24 outlines rather than an icon package: no extra dependency,
 * a consistent 1.6px stroke, and a set small enough to read. Every icon is
 * decorative (`aria-hidden`) — labels always carry the meaning, so a screen
 * reader never depends on a glyph.
 */
export type IconName =
  | 'leaf'
  | 'home'
  | 'chat'
  | 'search'
  | 'shield'
  | 'database'
  | 'info'
  | 'alert'
  | 'check'
  | 'book'
  | 'menu'
  | 'close'
  | 'arrow-right'
  | 'arrow-left'
  | 'chevron-down'
  | 'external'
  | 'document'
  | 'clock'
  | 'spark'
  | 'user'
  | 'sprout'
  | 'globe'

const PATHS: Record<IconName, JSX.Element> = {
  leaf: (
    <>
      <path d="M4 20c0-8 5-14 16-15 .5 9-4.5 15-12 15H4Z" />
      <path d="M4 20c3-5 7-8 12-10" />
    </>
  ),
  home: (
    <>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1v-9.5Z" />
    </>
  ),
  chat: (
    <>
      <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H9l-4 3.5V6.5Z" />
      <path d="M8.5 9.5h7" />
      <path d="M8.5 12.5h4" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 4.5 4.5" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3.5 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-2.5Z" />
      <path d="m9 12 2.2 2.2L15.5 10" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="6" rx="7" ry="3" />
      <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
      <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5.5" />
      <path d="M12 7.6h.01" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4.5 3.5 19h17L12 4.5Z" />
      <path d="M12 10v4" />
      <path d="M12 16.8h.01" />
    </>
  ),
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  book: (
    <>
      <path d="M5 4.5h9a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3V4.5Z" />
      <path d="M9 8.5h5" />
      <path d="M17 7.5h2v12H8" />
    </>
  ),
  menu: (
    <>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </>
  ),
  close: (
    <>
      <path d="m6 6 12 12" />
      <path d="m18 6-12 12" />
    </>
  ),
  'arrow-right': (
    <>
      <path d="M4 12h15" />
      <path d="m13 6 6 6-6 6" />
    </>
  ),
  'arrow-left': (
    <>
      <path d="M20 12H5" />
      <path d="m11 18-6-6 6-6" />
    </>
  ),
  'chevron-down': <path d="m6 9.5 6 6 6-6" />,
  external: (
    <>
      <path d="M14 4h6v6" />
      <path d="M20 4 11 13" />
      <path d="M18 14v5.5H4.5V5.5H10" />
    </>
  ),
  document: (
    <>
      <path d="M6 3.5h8l4 4V20.5H6V3.5Z" />
      <path d="M14 3.5v4h4" />
      <path d="M9 12h6" />
      <path d="M9 16h6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  spark: (
    <>
      <path d="M12 3.5 13.6 9l5.4 1.6-5.4 1.6L12 17.5 10.4 12 5 10.6 10.4 9 12 3.5Z" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M5 20c1.2-3.6 3.8-5.5 7-5.5s5.8 1.9 7 5.5" />
    </>
  ),
  sprout: (
    <>
      <path d="M12 21v-7" />
      <path d="M12 14c0-3.3-2.7-6-6-6 0 3.3 2.7 6 6 6Z" />
      <path d="M12 14c0-3.9 3.1-7 7-7 0 3.9-3.1 7-7 7Z" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17" />
      <path d="M12 3.5c2.2 2.3 3.4 5.3 3.4 8.5S14.2 18.2 12 20.5c-2.2-2.3-3.4-5.3-3.4-8.5S9.8 5.8 12 3.5Z" />
    </>
  ),
}

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName
  className?: string
}

export function Icon({ name, className = 'h-5 w-5', ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  )
}
