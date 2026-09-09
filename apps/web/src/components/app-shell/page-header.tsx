import type { ReactNode } from "react"

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="flex flex-col gap-4 pb-1 sm:flex-row sm:items-end sm:justify-between">
    <div className="space-y-2">
      {eyebrow && <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{eyebrow}</p>}
      <h1 className="text-2xl font-semibold tracking-[-0.035em] sm:text-[30px] sm:leading-10">{title}</h1>
      <p className="max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
    {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
  </header>
}
