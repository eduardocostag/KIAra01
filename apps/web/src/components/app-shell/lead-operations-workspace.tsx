"use client"

import { useMemo, useState } from "react"
import { ArrowRight, MessageCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { leadDisplayName, normalizeWhatsAppPhone, whatsappComposerUrl, type PipelineEntry } from "@/lib/api/pipeline"
import { cn } from "@/lib/utils"

type QueueFilter = "all" | "overdue" | "replied" | "ready" | "missing"

function whatsappActivity(entry: PipelineEntry) {
  return entry.activities?.filter((activity) => activity.channel === "whatsapp")
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0]
}

function hasWhatsApp(entry: PipelineEntry) {
  return Boolean(entry.consumer.whatsapp_url || normalizeWhatsAppPhone(entry.consumer.phone))
}

function isOverdue(entry: PipelineEntry, now: number) {
  return Boolean(entry.next_action_at && Date.parse(entry.next_action_at) < now)
}

/** One state per lead, ordered by how urgently a person should act on it. */
function stateFor(entry: PipelineEntry, now: number) {
  const activity = whatsappActivity(entry)
  if (isOverdue(entry, now)) return { id: "overdue", label: "Ação atrasada", tone: "text-amber-400", priority: 0 }
  if (activity?.status === "replied") return { id: "replied", label: "Respondeu", tone: "text-emerald-400", priority: 1 }
  if (!hasWhatsApp(entry)) return { id: "missing", label: "Sem WhatsApp", tone: "text-muted-foreground", priority: 4 }
  if (activity?.status === "sent" || activity?.status === "opened") return { id: "waiting", label: "Aguardando retorno", tone: "text-muted-foreground", priority: 3 }
  if (activity?.status === "no_response") return { id: "waiting", label: "Sem resposta", tone: "text-muted-foreground", priority: 3 }
  return { id: "ready", label: "Pronto para contato", tone: "text-primary", priority: 2 }
}

const filters: { id: QueueFilter; label: string }[] = [
  { id: "all", label: "Todos" },
  { id: "overdue", label: "Atrasados" },
  { id: "replied", label: "Responderam" },
  { id: "ready", label: "Prontos para contato" },
  { id: "missing", label: "Sem WhatsApp" },
]

export function LeadOperationsWorkspace({ entries, onOpen }: { entries: PipelineEntry[]; onOpen: (entryId: string) => void }) {
  const [filter, setFilter] = useState<QueueFilter>("all")
  const [now] = useState(() => Date.now())
  const queue = useMemo(() => entries
    .filter((entry) => entry.stage !== "won" && entry.stage !== "lost")
    .map((entry) => ({ entry, state: stateFor(entry, now) }))
    .sort((left, right) => left.state.priority - right.state.priority
      || (Date.parse(left.entry.next_action_at ?? "") || Infinity) - (Date.parse(right.entry.next_action_at ?? "") || Infinity)), [entries, now])
  const counts = useMemo(() => Object.fromEntries(filters.map((item) => [item.id, item.id === "all" ? queue.length : queue.filter(({ state }) => state.id === item.id).length])) as Record<QueueFilter, number>, [queue])
  const visible = filter === "all" ? queue : queue.filter(({ state }) => state.id === filter)

  return <section aria-label="Fila do dia" className="space-y-4">
    <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] lg:mx-0 lg:flex-wrap lg:px-0" role="group" aria-label="Filtrar fila">
      {filters.map((item) => <button key={item.id} type="button" aria-pressed={filter === item.id} onClick={() => setFilter(item.id)} className={cn("shrink-0 rounded-full border px-3 py-1.5 text-sm transition", filter === item.id ? "border-primary/50 bg-primary/15" : "border-transparent text-muted-foreground hover:text-foreground")}>
        {item.label} <span className="tabular-nums text-muted-foreground">{counts[item.id]}</span>
      </button>)}
    </div>
    {visible.length ? <ul className="divide-y overflow-hidden rounded-xl border bg-card">
      {visible.map(({ entry, state }) => {
        const name = leadDisplayName(entry.consumer)
        const whatsapp = whatsappComposerUrl(entry.consumer.phone, entry.consumer.whatsapp_url, "")
        return <li key={entry.id} className="flex items-center gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{name}</p>
            <p className="truncate text-xs text-muted-foreground">{entry.next_action || "Sem próxima ação definida"}</p>
          </div>
          <span className={cn("hidden shrink-0 text-xs font-medium sm:block", state.tone)}>{state.label}</span>
          {whatsapp ? <Button asChild size="icon" variant="ghost" className="size-8 shrink-0"><a href={whatsapp.url} target="_blank" rel="noopener noreferrer" aria-label={`Abrir WhatsApp de ${name}`}><MessageCircle /></a></Button> : null}
          <Button size="sm" variant="outline" className="shrink-0" onClick={() => onOpen(entry.id)}>Abrir<ArrowRight /></Button>
        </li>
      })}
    </ul> : <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Nada nesta fila agora.</p>}
  </section>
}
