"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, Check, Clock3, Loader2, MapPin, RefreshCw, Search, Sparkles, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { leadDisplayName, parsePipeline, pipelineStages, requestPipeline, sourceLabels, type PipelineEntry, type PipelineStage, websiteLabel } from "@/lib/api/pipeline"
import { cn } from "@/lib/utils"

const stageColors: Record<PipelineStage, string> = { new: "border-sky-500/30 bg-sky-500/8", qualified: "border-violet-500/30 bg-violet-500/8", contacted: "border-amber-500/30 bg-amber-500/8", opportunity: "border-fuchsia-500/30 bg-fuchsia-500/8", won: "border-emerald-500/30 bg-emerald-500/8", lost: "border-zinc-500/30 bg-zinc-500/8" }
const dotColors: Record<PipelineStage, string> = { new: "bg-sky-500", qualified: "bg-violet-500", contacted: "bg-amber-500", opportunity: "bg-fuchsia-500", won: "bg-emerald-500", lost: "bg-zinc-500" }

export function PipelineBoard({ initialEntries }: { initialEntries: PipelineEntry[] }) {
  const [entries, setEntries] = useState(initialEntries)
  const [selectedId, setSelectedId] = useState(initialEntries[0]?.id ?? "")
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const selected = entries.find((entry) => entry.id === selectedId) ?? null
  const filtered = useMemo(() => entries.filter((entry) => `${leadDisplayName(entry.consumer)} ${entry.consumer.research_query ?? ""} ${entry.consumer.address ?? ""}`.toLocaleLowerCase("pt-BR").includes(query.toLocaleLowerCase("pt-BR"))), [entries, query])
  const grouped = pipelineStages.map((stage) => ({ ...stage, entries: filtered.filter((entry) => entry.stage === stage.id) }))

  async function refresh() {
    setLoading(true); setError("")
    try { const next = parsePipeline(await requestPipeline("/api/pipeline")); setEntries(next); setSelectedId((current) => next.some((entry) => entry.id === current) ? current : next[0]?.id ?? "") }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível atualizar o Pipeline.") }
    finally { setLoading(false) }
  }

  async function updateSelected(changes: { stage?: PipelineStage; next_action?: string | null }) {
    if (!selected) return
    setSaving(true); setError(""); setNotice("")
    try {
      const updated = parsePipeline({ items: [await requestPipeline(`/api/pipeline/${encodeURIComponent(selected.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "If-Match": `"${selected.version}"`, "Idempotency-Key": `pipeline-${selected.id}-${Date.now()}` }, body: JSON.stringify(changes) })] })[0]
      setEntries((current) => current.map((entry) => entry.id === updated.id ? updated : entry)); setNotice(`${leadDisplayName(updated.consumer)} foi atualizado.`)
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível atualizar o Pipeline.") }
    finally { setSaving(false) }
  }

  return <div className="mx-auto max-w-[1500px] space-y-6">
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.14em] text-primary"><Sparkles className="size-3.5" />Organização comercial</p><h1 className="kiara-editorial mt-2 text-4xl">Pipeline</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Acompanhe cada lead da descoberta ao fechamento, defina a próxima ação e mantenha a operação em movimento.</p></div><div className="flex flex-wrap gap-2"><div className="relative min-w-56 flex-1"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 pl-9" placeholder="Buscar leads" aria-label="Buscar leads no Pipeline" /></div><Button variant="outline" onClick={() => void refresh()} disabled={loading}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}Atualizar</Button><Button asChild><Link href="/app/hunter">Nova pesquisa<ArrowRight /></Link></Button></div></header>
    {error && <div role="alert" className="flex items-start gap-3 rounded-xl border border-destructive/25 bg-destructive/5 p-4 text-sm text-destructive"><TriangleAlert className="mt-0.5 size-4 shrink-0" />{error}</div>}
    {notice && <div role="status" className="flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3 text-sm text-emerald-700"><Check className="size-4" />{notice}</div>}
    {!entries.length ? <div className="grid min-h-72 place-items-center rounded-2xl border border-dashed p-8 text-center"><div><h2 className="text-xl font-semibold">Seu Pipeline começa com uma pesquisa</h2><p className="mt-2 text-sm text-muted-foreground">Encontre leads no Hunter e organize cada oportunidade nesta visão.</p><Button asChild className="mt-5"><Link href="/app/hunter">Pesquisar leads<ArrowRight /></Link></Button></div></div> : <><div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">{grouped.map((stage) => <div key={stage.id} className="rounded-xl border bg-card p-3"><div className="flex items-center gap-2"><span className={cn("size-2 rounded-full", dotColors[stage.id])} /><span className="text-xs font-semibold text-muted-foreground">{stage.label}</span></div><strong className="mt-2 block text-2xl tabular-nums">{stage.entries.length}</strong></div>)}</div><div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]"><div className="min-w-0 overflow-x-auto pb-3"><div className="grid min-w-[1596px] grid-cols-6 gap-4">{grouped.map((stage) => <section key={stage.id} className={cn("min-w-0 rounded-2xl border p-3", stageColors[stage.id])} aria-labelledby={`stage-${stage.id}`}><header className="flex items-center justify-between gap-2 px-1 pb-3"><h2 id={`stage-${stage.id}`} className="text-sm font-semibold">{stage.label}</h2><span className="text-xs tabular-nums text-muted-foreground">{stage.entries.length}</span></header><div className="space-y-2">{stage.entries.map((entry) => <button key={entry.id} type="button" onClick={() => { setSelectedId(entry.id); setNotice("") }} className={cn("w-full min-w-0 rounded-xl border bg-card p-3 text-left shadow-sm transition hover:border-primary/40", selected?.id === entry.id && "border-primary ring-2 ring-primary/15")}><div className="flex min-w-0 items-start gap-2"><span className={cn("mt-1.5 size-2 shrink-0 rounded-full", dotColors[entry.stage])} /><span className="min-w-0"><strong className="block truncate text-sm">{leadDisplayName(entry.consumer)}</strong><small className="mt-1 block truncate text-muted-foreground">{entry.next_action || "Definir próxima ação"}</small></span></div>{entry.next_action_at && <span className="mt-3 flex items-center gap-1 text-[11px] text-muted-foreground"><Clock3 className="size-3" />{new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(new Date(entry.next_action_at))}</span>}</button>)}</div></section>)}</div></div><PipelineInspector entry={selected} saving={saving} onUpdate={updateSelected} /></div></>}
  </div>
}

function PipelineInspector({ entry, saving, onUpdate }: { entry: PipelineEntry | null; saving: boolean; onUpdate: (changes: { stage?: PipelineStage; next_action?: string | null }) => Promise<void> }) {
  const [stage, setStage] = useState<PipelineStage>(entry?.stage ?? "new")
  const [nextAction, setNextAction] = useState(entry?.next_action ?? "")
  if (!entry) return <aside className="rounded-2xl border bg-card p-6 text-sm text-muted-foreground">Selecione um lead para organizar sua próxima etapa.</aside>
  if (stage !== entry.stage && nextAction === (entry.next_action ?? "")) setStage(entry.stage)
  return <aside className="h-fit rounded-2xl border bg-card p-5 xl:sticky xl:top-6"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.12em] text-primary">Lead selecionado</p><h2 className="mt-2 break-words text-xl font-semibold">{leadDisplayName(entry.consumer)}</h2></div><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} className="text-muted-foreground hover:text-primary" aria-label="Abrir dossiê"><ArrowRight className="size-4" /></Link></div><div className="mt-5 space-y-4"><div className="rounded-xl bg-muted/40 p-3 text-sm"><p className="flex items-center gap-2 font-medium"><MapPin className="size-4 text-primary" />{entry.consumer.address || "Localização não informada"}</p><p className="mt-2 text-xs text-muted-foreground">{sourceLabels[entry.consumer.source ?? ""] ?? "Origem não informada"} · {websiteLabel(entry.consumer.website_status)}</p></div><div className="grid gap-2"><label htmlFor="pipeline-stage" className="text-sm font-medium">Etapa</label><select id="pipeline-stage" value={stage} onChange={(event) => setStage(event.target.value as PipelineStage)} className="h-10 rounded-md border bg-background px-3 text-sm">{pipelineStages.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></div><div className="grid gap-2"><label htmlFor="pipeline-next-action" className="text-sm font-medium">Próxima ação</label><Input id="pipeline-next-action" value={nextAction} onChange={(event) => setNextAction(event.target.value)} placeholder="Ex.: Enviar proposta até sexta" /></div><Button className="w-full" disabled={saving} onClick={() => void onUpdate({ stage, next_action: nextAction.trim() || null })}>{saving ? <Loader2 className="animate-spin" /> : <Check />}Salvar avanço</Button><Button asChild variant="outline" className="w-full"><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`}>Ver informações do lead<ArrowRight /></Link></Button></div></aside>
}
