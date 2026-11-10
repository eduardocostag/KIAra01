"use client"

import { useMemo, useState } from "react"
import { ArrowDown, ArrowUp, Clock3, MessageCircle, Search, TriangleAlert } from "lucide-react"
import { Input } from "@/components/ui/input"
import { leadDisplayName, type PipelineEntry } from "@/lib/api/pipeline"

type QueueFilter = "all" | "attention" | "overdue" | "replied" | "ready" | "missing"

const filters: { id: QueueFilter; label: string }[] = [
  { id: "all", label: "Todos" },
  { id: "attention", label: "Precisam de atenção" },
  { id: "overdue", label: "Follow-up vencido" },
  { id: "replied", label: "Responder / qualificar" },
  { id: "ready", label: "Prontos para contato" },
  { id: "missing", label: "Dados faltantes" },
]

function whatsappActivity(entry: PipelineEntry) {
  return entry.activities?.filter((activity) => activity.channel === "whatsapp")
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0]
}

function hasWhatsApp(entry: PipelineEntry) {
  const digits = entry.consumer.phone?.replace(/\D/g, "") ?? ""
  return Boolean(entry.consumer.whatsapp_url || /^55\d{10,11}$/.test(digits))
}

function isOverdue(entry: PipelineEntry, now: number) {
  return Boolean(entry.next_action_at && Date.parse(entry.next_action_at) < now)
}

function stateFor(entry: PipelineEntry, now: number) {
  const activity = whatsappActivity(entry)
  if (isOverdue(entry, now)) return { label: "Follow-up vencido", tone: "text-destructive", priority: 0 }
  if (activity?.status === "replied") return { label: "Resposta registrada · qualificar", tone: "text-emerald-600 dark:text-emerald-400", priority: 1 }
  if (!hasWhatsApp(entry)) return { label: "Falta telefone de WhatsApp", tone: "text-amber-600 dark:text-amber-400", priority: 2 }
  if (activity?.status === "opened") return { label: "Conversa aberta · envio não confirmado", tone: "text-amber-600 dark:text-amber-400", priority: 3 }
  if (activity?.status === "sent") return { label: "Aguardando retorno", tone: "text-muted-foreground", priority: 4 }
  if (activity?.status === "no_response") return { label: "Sem resposta registrada", tone: "text-muted-foreground", priority: 3 }
  if (entry.stage === "opportunity") return { label: "Oportunidade em andamento", tone: "text-primary", priority: 2 }
  return { label: "Pronto para primeiro contato", tone: "text-primary", priority: 5 }
}

function missingFor(entry: PipelineEntry) {
  const missing: string[] = []
  if (!hasWhatsApp(entry)) missing.push("telefone/WhatsApp")
  if (!entry.consumer.email?.trim()) missing.push("e-mail")
  if (!entry.consumer.address?.trim()) missing.push("localização")
  if (!entry.consumer.notes?.trim()) missing.push("contexto ou observações")
  return missing
}

function dateLabel(value: string | null | undefined) {
  if (!value) return "Sem prazo definido"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Data indisponível"
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(date)
}

export function LeadOperationsWorkspace({ entries }: { entries: PipelineEntry[] }) {
  const [filter, setFilter] = useState<QueueFilter>("all")
  const [query, setQuery] = useState("")
  const [selectedId, setSelectedId] = useState("")
  const [page, setPage] = useState(1)
  const [now] = useState(() => Date.now())
  const activeEntries = useMemo(() => entries.filter((entry) => !["won", "lost"].includes(entry.stage)), [entries])
  const counts = useMemo(() => ({
    overdue: activeEntries.filter((entry) => isOverdue(entry, now)).length,
    replied: activeEntries.filter((entry) => whatsappActivity(entry)?.status === "replied").length,
    ready: activeEntries.filter((entry) => hasWhatsApp(entry) && !whatsappActivity(entry) && !isOverdue(entry, now)).length,
    missing: activeEntries.filter((entry) => !hasWhatsApp(entry)).length,
    missingInfo: activeEntries.filter((entry) => missingFor(entry).length > 0).length,
    attention: activeEntries.filter((entry) => isOverdue(entry, now) || whatsappActivity(entry)?.status === "replied" || !hasWhatsApp(entry)).length,
  }), [activeEntries, now])

  const filtered = useMemo(() => {
    const search = query.trim().toLocaleLowerCase("pt-BR")
    return activeEntries.filter((entry) => {
      const activity = whatsappActivity(entry)
      const state = stateFor(entry, now)
      const matchesFilter = filter === "all" ||
        (filter === "attention" && (isOverdue(entry, now) || activity?.status === "replied" || !hasWhatsApp(entry))) ||
        (filter === "overdue" && isOverdue(entry, now)) ||
        (filter === "replied" && activity?.status === "replied") ||
        (filter === "ready" && hasWhatsApp(entry) && !activity && !isOverdue(entry, now)) ||
        (filter === "missing" && missingFor(entry).length > 0)
      const searchable = `${leadDisplayName(entry.consumer)} ${entry.consumer.display_name} ${entry.consumer.phone ?? ""} ${entry.consumer.email ?? ""} ${entry.next_action ?? ""} ${state.label}`.toLocaleLowerCase("pt-BR")
      return matchesFilter && (!search || searchable.includes(search))
    }).sort((a, b) => {
      const priority = stateFor(a, now).priority - stateFor(b, now).priority
      if (priority) return priority
      const aDue = a.next_action_at ? Date.parse(a.next_action_at) : Number.MAX_SAFE_INTEGER
      const bDue = b.next_action_at ? Date.parse(b.next_action_at) : Number.MAX_SAFE_INTEGER
      return aDue - bDue || Date.parse(b.updated_at) - Date.parse(a.updated_at)
    })
  }, [activeEntries, filter, now, query])

  const pageSize = 50
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const pageEntries = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const selected = pageEntries.find((entry) => entry.id === selectedId) ?? pageEntries[0]
  const selectedActivity = selected ? whatsappActivity(selected) : undefined
  const missing = selected ? missingFor(selected) : []

  function changeFilter(value: QueueFilter) {
    setFilter(value)
    setPage(1)
    setSelectedId("")
  }

  function changeQuery(value: string) {
    setQuery(value)
    setPage(1)
    setSelectedId("")
  }

  return <section className="space-y-4" aria-label="Central de operação de leads">
    <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <MessageCircle className="mt-0.5 size-5 shrink-0 text-primary" />
        <div><h2 className="font-semibold">Central de operação</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">A fila organiza os leads por prioridade, próximas ações e dados faltantes. Consulte mensagens e estados de envio na Caixa de entrada. A leitura e o envio pelo WhatsApp dependem do executor conectado e da operação habilitada.</p></div>
      </div>
    </div>

    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <Summary label="Leads ativos" value={activeEntries.length} />
      <Summary label="Precisam de atenção" value={counts.attention} tone="text-primary" />
      <Summary label="Follow-ups vencidos" value={counts.overdue} tone={counts.overdue ? "text-destructive" : ""} />
      <Summary label="Respostas para qualificar" value={counts.replied} tone="text-emerald-600 dark:text-emerald-400" />
      <Summary label="Sem WhatsApp válido" value={counts.missing} tone={counts.missing ? "text-amber-600 dark:text-amber-400" : ""} />
    </div>

    <div className="overflow-hidden rounded-2xl border bg-card">
      <div className="space-y-3 border-b p-4">
        <div className="relative"><Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => changeQuery(event.target.value)} className="pl-9" placeholder="Buscar por nome, telefone, e-mail ou ação" aria-label="Buscar leads na fila" /></div>
        <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Filtrar fila">
          {filters.map((item) => <button key={item.id} type="button" aria-pressed={filter === item.id} onClick={() => changeFilter(item.id)} className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${filter === item.id ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted"}`}>
            {item.label}{item.id === "overdue" ? ` · ${counts.overdue}` : item.id === "replied" ? ` · ${counts.replied}` : item.id === "ready" ? ` · ${counts.ready}` : item.id === "missing" ? ` · ${counts.missingInfo}` : ""}
          </button>)}
        </div>
      </div>

      <div className="grid min-h-[480px] lg:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
        <div className="min-w-0 border-b lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between px-4 py-3 text-xs text-muted-foreground"><span>{filtered.length ? `${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, filtered.length)} de ${filtered.length} leads` : "Nenhum lead nesta fila"}</span><span>Ordenados por prioridade</span></div>
          {pageEntries.length ? <ul className="divide-y">{pageEntries.map((entry) => {
            const state = stateFor(entry, now)
            const active = selected?.id === entry.id
            return <li key={entry.id}><button type="button" onClick={() => setSelectedId(entry.id)} aria-pressed={active} className={`w-full px-4 py-3 text-left transition-colors ${active ? "bg-primary/5" : "hover:bg-muted/50"}`}>
              <span className="flex items-start justify-between gap-3"><span className="min-w-0"><strong className="block truncate text-sm">{leadDisplayName(entry.consumer)}</strong><span className="mt-1 block truncate text-xs text-muted-foreground">{entry.consumer.phone || "Sem telefone"}{entry.consumer.email ? ` · ${entry.consumer.email}` : ""}</span></span><span className={`shrink-0 text-right text-xs font-medium ${state.tone}`}>{state.label}</span></span>
              <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"><span>Etapa: {entry.stage}</span><span>{entry.next_action || (entry.next_action_at ? "Próxima ação agendada" : "Sem próxima ação")}</span></span>
            </button></li>
          })}</ul> : <div className="grid min-h-56 place-items-center p-6 text-center text-sm text-muted-foreground">Nenhum lead corresponde a este filtro.</div>}
          <div className="flex items-center justify-between border-t p-3">
            <span className="text-xs text-muted-foreground">Mostrando até 50 leads por página</span>
            <div className="flex items-center gap-2"><button type="button" className="grid size-8 place-items-center rounded-md border disabled:opacity-40" aria-label="Página anterior" disabled={currentPage <= 1} onClick={() => { setPage((value) => Math.max(1, value - 1)); setSelectedId("") }}><ArrowUp className="size-4" /></button><span className="text-xs tabular-nums">{currentPage} / {pageCount}</span><button type="button" className="grid size-8 place-items-center rounded-md border disabled:opacity-40" aria-label="Próxima página" disabled={currentPage >= pageCount} onClick={() => { setPage((value) => Math.min(pageCount, value + 1)); setSelectedId("") }}><ArrowDown className="size-4" /></button></div>
          </div>
        </div>

        <aside className="min-w-0 p-4 sm:p-5" aria-label={selected ? `Resumo do lead ${leadDisplayName(selected.consumer)}` : "Resumo do lead"}>
          {selected ? <>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Resumo do lead</p>
            <h3 className="mt-2 break-words text-lg font-semibold">{leadDisplayName(selected.consumer)}</h3>
            <dl className="mt-4 space-y-3 text-sm">
              <Detail label="Estado atual" value={stateFor(selected, now).label} />
              <Detail label="Etapa do CRM" value={selected.stage} />
              <Detail label="Telefone" value={selected.consumer.phone || "Não cadastrado"} />
              <Detail label="Próxima ação" value={selected.next_action || "Não definida"} />
              <Detail label="Prazo da ação" value={dateLabel(selected.next_action_at)} />
            </dl>
            <div className="mt-5 rounded-xl border p-3">
              <h4 className="flex items-center gap-2 text-sm font-semibold"><TriangleAlert className="size-4 text-amber-500" />O que falta</h4>
              {missing.length ? <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-muted-foreground">{missing.map((item) => <li key={item}>Completar {item}</li>)}</ul> : <p className="mt-2 text-xs text-muted-foreground">Dados básicos de contato e contexto preenchidos.</p>}
              {stateFor(selected, now).priority === 1 ? <p className="mt-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">Revisar a resposta, qualificar a necessidade e registrar o próximo passo.</p> : null}
              {isOverdue(selected, now) ? <p className="mt-2 text-xs font-medium text-destructive">A ação está vencida; revisar e reagendar no CRM.</p> : null}
            </div>
            <div className="mt-5 border-t pt-4">
              <h4 className="flex items-center gap-2 text-sm font-semibold"><Clock3 className="size-4" />Última atividade de WhatsApp</h4>
              {selectedActivity ? <div className="mt-2 space-y-1 text-xs"><p className="font-medium">{selectedActivity.status === "sent" ? "Envio registrado" : selectedActivity.status === "replied" ? "Resposta registrada" : selectedActivity.status === "opened" ? "Conversa aberta, sem confirmação de envio" : "Sem resposta"}</p><p className="whitespace-pre-wrap break-words text-muted-foreground">{selectedActivity.body || "Sem conteúdo registrado."}</p><time className="block text-muted-foreground" dateTime={selectedActivity.created_at}>{dateLabel(selectedActivity.created_at)}</time></div> : <p className="mt-2 text-xs text-muted-foreground">Ainda não há atividade de WhatsApp registrada no CRM.</p>}
            </div>
          </> : <p className="text-sm text-muted-foreground">Selecione um lead para ver o resumo operacional.</p>}
        </aside>
      </div>
    </div>
  </section>
}

function Summary({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return <div className="rounded-xl border bg-card p-3 sm:p-4"><p className="text-xs text-muted-foreground">{label}</p><p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value.toLocaleString("pt-BR")}</p></div>
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="grid grid-cols-[minmax(90px,.7fr)_minmax(0,1fr)] gap-3"><dt className="text-muted-foreground">{label}</dt><dd className="break-words text-right font-medium">{value}</dd></div>
}
