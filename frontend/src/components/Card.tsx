import type { PropsWithChildren } from 'react'

interface CardProps {
  className?: string
  /** Raises the panel and its shadow on hover. For cards that are themselves a link. */
  interactive?: boolean
}

/** The single panel surface used across the product. */
export function Card({ children, className = '', interactive = false }: PropsWithChildren<CardProps>) {
  return (
    <div
      className={
        'rounded-card border border-ivory-300 bg-white shadow-card ' +
        (interactive
          ? 'transition-[box-shadow,transform,border-color] duration-300 ease-out hover:-translate-y-0.5 hover:border-sage-300 hover:shadow-lift motion-reduce:transform-none '
          : '') +
        className
      }
    >
      {children}
    </div>
  )
}

interface SectionProps {
  title: string
  icon?: React.ReactNode
  aside?: React.ReactNode
  children: React.ReactNode
  className?: string
  bodyClassName?: string
}

/** A titled block inside a card: label, optional aside, then content. */
export function Section({
  title,
  icon,
  aside,
  children,
  className = '',
  bodyClassName = 'px-5 py-4 sm:px-6 sm:py-5',
}: SectionProps) {
  return (
    <section className={className}>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-ivory-200 px-5 py-3.5 sm:px-6">
        <h2 className="flex items-center gap-2 font-display text-[15px] font-semibold text-ink-900">
          {icon}
          {title}
        </h2>
        {aside}
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}
