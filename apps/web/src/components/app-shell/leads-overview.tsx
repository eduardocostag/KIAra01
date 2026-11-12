import Link from "next/link"
import { ArrowRight, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { leadDisplayName, pipelineStages, type PipelineEntry } from "@/lib/api/pipeline"

function relativeTime(value: string, now: number) {
  const minutes = Math.floor((now - new Date(value).getTime()) / 60000)
  if (!Number.isFinite(minutes)) return "—"
  if (minutes < 1) return "agora"
  if (minutes < 60) return `há ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `há ${hours} h`
  const days = Math.floor(hours / 24)
  return `há ${days} ${days === 1 ? "dia" : "dias"}`
}

function dueLabel(value: string | null | undefined, now: number) {
  if (!value) return "Sem data"
  const time = Date.parse(value)
  if (Number.isNaN(time)) return "Sem data"
  if (time < now) return "Atrasada"
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }).format(time)
}

const stageLabel = (stage: PipelineEntry["stage"]) => pipelineStages.find((item) => item.id === stage)?.label ?? stage
const contactHref = (entry: PipelineEntry) => `/app/pipeline?contact=${encodeURIComponent(entry.id)}`

/** Leads home: what needs attention today, without marketing copy. */
export function LeadsOverview({ entries, available, now }: { entries: PipelineEntry[]; available: boolean; now: number }) {
  const active = entries.filter((entry) => entry.stage !== "won" && entry.stage !== "lost")
  const fresh = active.filter((entry) => entry.stage === "new")
  const withAction = active.filter((entry) => entry.next_action?.trim())
    .sort((left, right) => (Date.parse(left.next_action_at ?? "") || Infinity) - (Date.parse(right.next_action_at ?? "") || Infinity))
  const overdue = withAction.filter((entry) => entry.next_action_at && Date.parse(entry.next_action_at) < now)
  const recent = [...entries].sort((left, right) => right.updated_at.localeCompare(left.updated_at)).slice(0, 5)
  const date = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", timeZone: "America/Sao_Paulo" }).format(now)
  const metrics = [
    { label: "Novos para abordar", value: fresh.length, href: "/app/pipeline" },
    { label: "Em andamento", value: active.length, href: "/app/pipeline" },
    { label: "Ações atrasadas", value: overdue.length, href: "/app/pipeline?view=queue", alert: overdue.length > 0 },
  ]

  return <div className="mx-auto w-full max-w-5xl space-y-8">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-sm capitalize text-muted-foreground">{date}</p>
        <h1 className="mt-1 text-3xl font-medium tracking-tight">Visão geral</h1>
      </div>
      <div className="flex gap-2">
        <Button asChild><Link href="/app/hunter"><Search />Buscar leads</Link></Button>
        <Button asChild variant="outline"><Link href="/app/pipeline">Contatos</Link></Button>
      </div>
    </header>

    {!available ? <p role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">Não foi possível carregar seus contatos. Atualize a página para tentar novamente.</p> : null}

    <section aria-label="Indicadores" className="grid gap-3 sm:grid-cols-3">
      {metrics.map((metric) => <Link key={metric.label} href={metric.href} className="rounded-xl border bg-card p-5 transition hover:border-primary/40">
        <p className={metric.alert ? "text-3xl font-semibold tabular-nums text-amber-400" : "text-3xl font-semibold tabular-nums"}>{available ? metric.value : "—"}</p>
        <p className="mt-1 text-sm text-muted-foreground">{metric.label}</p>
      </Link>)}
    </section>

    <div className="grid gap-6 lg:grid-cols-2">
      <section aria-labelledby="next-actions-title" className="space-y-3">
        <h2 id="next-actions-title" className="font-semibold">Próximas ações</h2>
        {withAction.length ? <ul className="divide-y overflow-hidden rounded-xl border bg-card">
          {withAction.slice(0, 5).map((entry) => {
            const due = dueLabel(entry.next_action_at, now)
            return <li key={entry.id}><Link href={contactHref(entry)} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/40">
              <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{entry.next_action}</span><span className="block truncate text-xs text-muted-foreground">{leadDisplayName(entry.consumer)}</span></span>
              <span className={due === "Atrasada" ? "shrink-0 text-xs font-medium text-amber-400" : "shrink-0 text-xs text-muted-foreground"}>{due}</span>
            </Link></li>
          })}
        </ul> : <p className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">Nenhuma ação agendada. Defina a próxima ação de cada contato para não perder oportunidades.</p>}
      </section>

      <section aria-labelledby="recent-title" className="space-y-3">
        <div className="flex items-center justify-between"><h2 id="recent-title" className="font-semibold">Leads recentes</h2><Link href="/app/pipeline" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">Ver todos<ArrowRight className="size-3.5" /></Link></div>
        {recent.length ? <ul className="divide-y overflow-hidden rounded-xl border bg-card">
          {recent.map((entry) => <li key={entry.id}><Link href={contactHref(entry)} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/40">
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{leadDisplayName(entry.consumer)}</span>
            <span className="shrink-0 text-xs text-muted-foreground">{stageLabel(entry.stage)} · {relativeTime(entry.updated_at, now)}</span>
          </Link></li>)}
        </ul> : <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">Seus primeiros leads aparecem aqui depois de uma busca. <Link href="/app/hunter" className="font-medium text-primary hover:underline">Buscar leads</Link></div>}
      </section>
    </div>
  </div>
}
