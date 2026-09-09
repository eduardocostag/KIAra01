"use client"

import Link from "next/link"
import { useMemo, useRef, useState, type ReactNode } from "react"
import { ArrowRight, AtSign, CheckCircle2, Clock3, Compass, Globe2, Loader2, MapPin, MessageCircle, Plus, RefreshCw, Search, Sparkles, Target } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { LeadContactActions } from "./lead-contact-actions"
import { parsePipeline, parsePipelineEntry, pipelineStages, requestPipeline, sourceLabels, type PipelineEntry, type PipelineStage, websiteLabel } from "@/lib/api/pipeline"

const stageColors: Record<PipelineStage, string> = { new: "bg-sky-500", qualified: "bg-violet-500", contacted: "bg-amber-500", opportunity: "bg-fuchsia-500", won: "bg-emerald-500", lost: "bg-zinc-400" }

export function PipelineWorkspace({ initialEntries, initialError = "" }: { initialEntries: PipelineEntry[]; initialError?: string }) {
  const [entries, setEntries] = useState(initialEntries)
  const [selectedId, setSelectedId] = useState(initialEntries[0]?.id ?? "")
  const [stageFilter, setStageFilter] = useState<PipelineStage | "all">("all")
  const [error, setError] = useState(initialError)
  const [notice, setNotice] = useState("")
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState<string[]>([])
  const inFlight = useRef(new Set<string>()), refreshing = useRef(false)
  const visible = useMemo(() => entries.filter((entry) => (stageFilter === "all" || entry.stage === stageFilter) && `${entry.consumer.display_name} ${entry.consumer.phone ?? ""} ${entry.consumer.research_query ?? ""}`.toLocaleLowerCase("pt-BR").includes(query.toLocaleLowerCase("pt-BR"))), [entries, query, stageFilter])
  const selected = entries.find((entry) => entry.id === selectedId) ?? visible[0] ?? entries[0]

  async function refresh() {
    if (refreshing.current || inFlight.current.size) return
    refreshing.current = true; setLoading(true); setError("")
    try { const next = parsePipeline(await requestPipeline("/api/pipeline")); setEntries(next); setSelectedId((current) => next.some((item) => item.id === current) ? current : next[0]?.id ?? "") }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível atualizar o Pipeline.") }
    finally { refreshing.current = false; setLoading(false) }
  }
  async function move(entry: PipelineEntry, stage: PipelineStage) {
    if (stage === entry.stage || inFlight.current.has(entry.id) || refreshing.current) return
    inFlight.current.add(entry.id); setSaving([...inFlight.current]); setError(""); setNotice("")
    try { const updated = parsePipelineEntry(await requestPipeline(`/api/pipeline/${encodeURIComponent(entry.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "If-Match": `"${entry.version}"`, "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ stage }) })); setEntries((current) => current.map((item) => item.id === entry.id ? updated : item)); setNotice(`${entry.consumer.display_name} agora está em ${pipelineStages.find((item) => item.id === stage)?.label}.`) }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível alterar a etapa.") }
    finally { inFlight.current.delete(entry.id); setSaving([...inFlight.current]) }
  }

  if (!entries.length && !error) return <div className="grid min-h-80 place-items-center rounded-3xl border border-dashed bg-card p-8 text-center"><div><Compass className="mx-auto size-9 text-primary" /><h2 className="mt-4 text-xl font-semibold">Sua central começa com um bom alvo</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">Use o Hunter para encontrar e validar os primeiros leads. Eles chegarão aqui prontos para a próxima decisão.</p><Button asChild className="mt-5"><Link href="/app/hunter">Abrir Hunter<ArrowRight /></Link></Button></div></div>

  return <div className="space-y-4">
    <section className="overflow-hidden rounded-3xl border bg-card shadow-[var(--shadow-2)]">
      <header className="relative overflow-hidden border-b bg-card px-5 py-5 text-foreground sm:px-7">
        <KiaraOrb size="sm" active className="absolute right-7 top-5 hidden 2xl:grid" />
        <div className="pointer-events-none absolute -right-16 -top-24 size-56 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between"><div><p className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-primary"><Sparkles className="size-3.5" />Kiara Copilot</p><h2 className="kiara-editorial mt-2 text-3xl font-medium tracking-tight">Uma decisão por vez.</h2><p className="mt-1 text-sm text-muted-foreground">Escolha um lead; a Kiara mostra somente o que ajuda na próxima ação.</p></div><div className="flex flex-wrap gap-2"><div className="relative min-w-52 flex-1 xl:w-72"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="h-10 bg-background pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nome, telefone ou pesquisa" /></div><Button variant="secondary" onClick={() => void refresh()} disabled={loading || saving.length > 0}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}Atualizar</Button><Button asChild><Link href="/app/hunter"><Plus />Novo alvo</Link></Button></div></div>
      </header>

      <div className="flex gap-2 overflow-x-auto border-b px-4 py-3 sm:px-6" aria-label="Filtrar etapa"><StageChip active={stageFilter === "all"} label="Todos" count={entries.length} onClick={() => setStageFilter("all")} />{pipelineStages.map((stage) => <StageChip key={stage.id} active={stageFilter === stage.id} label={stage.label} count={entries.filter((entry) => entry.stage === stage.id).length} dot={stageColors[stage.id]} onClick={() => setStageFilter(stage.id)} />)}</div>

      {error ? <div role="alert" className="m-4 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div> : null}<p className="sr-only" role="status">{notice}</p>
      <div className="grid min-h-[620px] lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b bg-muted/20 lg:border-b-0 lg:border-r"><div className="flex items-center justify-between px-4 py-3"><p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Fila inteligente</p><span className="text-xs tabular-nums text-muted-foreground">{visible.length}</span></div><div className="max-h-[560px] space-y-1 overflow-y-auto p-2">
          {visible.length ? visible.map((entry) => <button key={entry.id} type="button" onClick={() => setSelectedId(entry.id)} className={cn("group w-full rounded-2xl border border-transparent p-3 text-left transition-all", selected?.id === entry.id ? "border-primary/20 bg-background shadow-sm" : "hover:bg-background/70")}><div className="flex items-start gap-3"><span className={cn("mt-1.5 size-2.5 shrink-0 rounded-full ring-4 ring-background", stageColors[entry.stage])} /><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2"><p className="truncate text-sm font-semibold">{entry.consumer.display_name}</p><span className="text-[10px] text-muted-foreground">{pipelineStages.find((item) => item.id === entry.stage)?.label}</span></div><p className="mt-1 truncate text-xs text-muted-foreground">{entry.next_action || "Revisar e abordar"}</p><div className="mt-2 flex items-center gap-2 text-muted-foreground">{entry.consumer.whatsapp_url || entry.consumer.phone ? <MessageCircle className="size-3.5" /> : null}{entry.consumer.instagram_username ? <AtSign className="size-3.5" /> : null}{entry.next_action_at ? <Clock3 className="size-3.5 text-primary" /> : null}<span className="ml-auto text-[10px] opacity-0 transition-opacity group-hover:opacity-100">Abrir →</span></div></div></div></button>) : <p className="p-8 text-center text-sm text-muted-foreground">Nenhum lead neste filtro.</p>}
        </div></aside>

        {selected ? <main className="min-w-0 p-5 sm:p-7"><div className="flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-start sm:justify-between"><div className="min-w-0"><p className="text-xs font-medium uppercase tracking-wider text-primary">Lead em foco</p><h3 className="mt-2 break-words text-2xl font-semibold tracking-tight sm:text-3xl">{selected.consumer.display_name}</h3><p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground"><span>{sourceLabels[selected.consumer.source ?? ""] ?? "CRM"}</span>{selected.consumer.address ? <><span>·</span><MapPin className="size-3.5" /><span>{selected.consumer.address}</span></> : null}</p></div><Button asChild variant="outline"><Link href={`/app/leads/${encodeURIComponent(selected.consumer.id)}`}>Ver dossiê<ArrowRight /></Link></Button></div>

          <section className="py-6"><p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Jornada comercial</p><div className="grid grid-cols-3 gap-2 sm:grid-cols-6">{pipelineStages.map((stage, index) => { const current = pipelineStages.findIndex((item) => item.id === selected.stage), active = index <= current; return <button key={stage.id} type="button" disabled={saving.includes(selected.id)} onClick={() => void move(selected, stage.id)} className={cn("relative rounded-xl border px-2 py-3 text-center text-[11px] font-medium transition-all", stage.id === selected.stage ? "border-primary bg-primary text-primary-foreground shadow-md" : active ? "border-primary/20 bg-primary/5 text-foreground" : "bg-muted/25 text-muted-foreground hover:bg-muted/60")}>{stage.label}</button> })}</div></section>

          <div className="grid gap-3 sm:grid-cols-3"><Signal icon={<MessageCircle />} label="Contato" value={selected.consumer.whatsapp_url ? "WhatsApp confirmado" : selected.consumer.phone ? "Número para verificar no WhatsApp" : selected.consumer.instagram_username ? "Instagram disponível" : "WhatsApp não encontrado"} /><Signal icon={<Globe2 />} label="Presença digital" value={websiteLabel(selected.consumer.website_status)} /><Signal icon={<Target />} label="Origem" value={selected.consumer.research_query || "Entrada manual"} /></div>

          <section className="mt-6 rounded-2xl border bg-muted/20 p-5"><div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Próximo movimento</p><p className="mt-2 text-lg font-semibold">{selected.next_action || "Conhecer o contexto e preparar a primeira abordagem"}</p>{selected.next_action_at ? <p className="mt-2 flex items-center gap-2 text-sm text-primary"><Clock3 className="size-4" />{new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(selected.next_action_at))}</p> : null}</div><LeadContactActions entry={selected} onRecorded={refresh} /></div></section>

          <section className="mt-6"><div className="flex items-center justify-between"><p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Pulso recente</p><span className="text-xs text-muted-foreground">{selected.activities?.length ?? 0} registros</span></div>{selected.activities?.length ? <div className="mt-3 grid gap-2 sm:grid-cols-3">{selected.activities.slice(0, 3).map((activity) => <div key={activity.id} className="rounded-xl border p-3"><div className="flex items-center gap-2 text-xs font-medium">{activity.status === "sent" ? <CheckCircle2 className="size-3.5 text-emerald-600" /> : <Clock3 className="size-3.5 text-amber-600" />}{activity.status === "sent" ? "Envio confirmado" : "Canal aberto"}</div><p className="mt-2 text-[11px] text-muted-foreground">{activity.channel} · {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(activity.created_at))}</p></div>)}</div> : <div className="mt-3 rounded-xl border border-dashed p-4 text-sm text-muted-foreground">Ainda sem abordagem. Comece pelo próximo movimento acima.</div>}</section>
        </main> : null}
      </div>
    </section>
  </div>
}

function StageChip({ active, label, count, dot, onClick }: { active: boolean; label: string; count: number; dot?: string; onClick: () => void }) { return <button type="button" onClick={onClick} className={cn("flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors", active ? "border-foreground bg-foreground text-background" : "bg-background hover:bg-muted")} >{dot ? <span className={cn("size-2 rounded-full", dot)} /> : null}{label}<span className={cn("tabular-nums", active ? "text-background/65" : "text-muted-foreground")}>{count}</span></button> }
function Signal({ icon, label, value }: { icon: ReactNode; label: string; value: string }) { return <div className="rounded-2xl border bg-card p-4"><div className="flex items-center gap-2 text-muted-foreground [&_svg]:size-4">{icon}<span className="text-xs">{label}</span></div><p className="mt-3 line-clamp-2 text-sm font-semibold">{value}</p></div> }
