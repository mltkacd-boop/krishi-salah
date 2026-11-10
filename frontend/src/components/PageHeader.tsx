interface PageHeaderProps {
  title: string
  description?: string
  eyebrow?: string
  actions?: React.ReactNode
}

export function PageHeader({ title, description, eyebrow, actions }: PageHeaderProps) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <p className="label-caps mb-1.5">{eyebrow}</p>}
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-ink-900 sm:text-[30px]">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-500">{description}</p>
        )}
      </div>
      {actions}
    </header>
  )
}
