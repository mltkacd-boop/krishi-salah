import type { ButtonHTMLAttributes, PropsWithChildren } from 'react'

type Variant = 'primary' | 'secondary' | 'quiet' | 'onDark'
type Size = 'md' | 'lg'

/*
 * Forest is the action colour, ivory the surround. The secondary button is a
 * hairline on paper rather than a second filled shape, so a page with two
 * actions still has one obvious next step; `onDark` is the same idea inverted
 * for the forest panels.
 */
const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-forest-700 text-white shadow-card hover:bg-forest-800 hover:shadow-raised active:bg-forest-900 disabled:bg-ivory-300 disabled:text-ink-600 disabled:shadow-none',
  secondary:
    'border border-ivory-400 bg-white text-ink-800 hover:border-forest-300 hover:text-forest-800 hover:shadow-card active:bg-ivory-50',
  quiet: 'text-forest-800 hover:bg-forest-50 active:bg-forest-100',
  onDark:
    'border border-sage-400/45 bg-white/5 text-ivory-50 hover:border-sage-400 hover:bg-white/10 active:bg-white/15',
}

const SIZES: Record<Size, string> = {
  // 44px minimum touch target, per the usability brief.
  md: 'min-h-[44px] px-4 text-sm',
  lg: 'min-h-[48px] px-5 text-[15px]',
}

/**
 * One button implementation for the whole product.
 *
 * `buttonClass` is exported so a router `<Link>` can look identical without
 * nesting an anchor inside a button (which would give keyboard users two
 * stops for one action).
 */
export function buttonClass(variant: Variant = 'primary', size: Size = 'md', extra = '') {
  return [
    'inline-flex items-center justify-center gap-2 rounded-field font-semibold',
    'transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-out',
    'active:translate-y-px motion-reduce:transform-none',
    VARIANTS[variant],
    SIZES[size],
    extra,
  ].join(' ')
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  children,
  ...rest
}: PropsWithChildren<ButtonProps>) {
  return (
    <button type={type} className={buttonClass(variant, size, className)} {...rest}>
      {children}
    </button>
  )
}
