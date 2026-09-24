import type { ReactNode } from "react"

export function PageHeader({ eyebrow, title, description, actions, compact = false, mobileMinimal = false }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode; compact?: boolean; mobileMinimal?: boolean }) {
  return <header className={`kiara-section-heading ${compact ? "is-compact" : ""} ${mobileMinimal ? "is-mobile-minimal" : ""} flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between`}>
    <div className={compact ? "space-y-1" : "space-y-2"}>
      {eyebrow && <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{eyebrow}</p>}
      <h1 className="kiara-page-title text-3xl font-medium tracking-[-0.045em] sm:text-[38px] sm:leading-10">{title}</h1>
      {description && <p className="max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>}
    </div>
    {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
  </header>
}
