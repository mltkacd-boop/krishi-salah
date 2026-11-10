interface PageHeaderProps {
  title: string
  description?: string
  eyebrow?: string
  actions?: React.ReactNode
}

export function PageHeader({ title, description, eyebrow, actions }: PageHeaderProps) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-ivory-300 pb-5 sm:mb-8 sm:pb-6">
      <div className="min-w-0">
        {eyebrow && (
          <p className="label-caps flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-forest-600" aria-hidden="true" />
            {eyebrow}
          </p>
        )}
        <h1 className="mt-2 text-[27px] font-semibold leading-tight tracking-[-0.025em] text-forest-900 sm:text-[34px]">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-600">{description}</p>
        )}
      </div>
      {actions}
    </header>
  )
}
