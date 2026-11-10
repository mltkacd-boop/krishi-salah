import type { ButtonHTMLAttributes, PropsWithChildren } from 'react'

type Variant = 'primary' | 'secondary' | 'quiet'
type Size = 'md' | 'lg'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-forest-700 text-white shadow-card hover:bg-forest-800 active:bg-forest-900 disabled:bg-forest-700/40 disabled:shadow-none',
  secondary:
    'border border-ivory-400 bg-white text-ink-800 hover:border-forest-300 hover:text-forest-800 active:bg-ivory-50',
  quiet: 'text-forest-800 hover:bg-forest-50 active:bg-forest-100',
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
    'inline-flex items-center justify-center gap-2 rounded-field font-semibold transition-colors duration-150',
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
