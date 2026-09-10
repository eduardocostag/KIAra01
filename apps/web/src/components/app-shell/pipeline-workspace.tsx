"use client"

import Link from "next/link"
import { useMemo, useRef, useState } from "react"
import { ArrowRight, AtSign, Clock3, Globe2, Loader2, MapPin, MessageCircle, Plus, RefreshCw, Search, Sparkles } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { LeadContactActions } from "./lead-contact-actions"
import { parsePipeline, parsePipelineEntry, pipelineStages, requestPipeline, sourceLabels, type PipelineEntry, type PipelineStage, websiteLabel } from "@/lib/api/pipeline"

const colors: Record<PipelineStage, string> = { new: "bg-sky-500", qualified: "bg-violet-500", contacted: "bg-amber-500", opportunity: "bg-fuchsia-500", won: "bg-emerald-500", lost: "bg-zinc-400" }

export function PipelineWorkspace({ initialEntries, initialError = "" }: { initialEntries: PipelineEntry[]; initialError?: string }) {
  const [entries, setEntries] = useState(initialEntries), [selectedId, setSelectedId] = useState(initialEntries[0]?.id ?? "")
  const [stageFilter, setStageFilter] = useState<PipelineStage | "all">("all"), [query, setQuery] = useState("")
  const [error, setError] = useState(initialError), [loading, setLoading] = useState(false), [saving, setSaving] = useState<string[]>([])
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
    if (stage === entry.stage || inFlight.current.has(entry.id)) return
    inFlight.current.add(entry.id); setSaving([...inFlight.current]); setError("")
    try { const updated = parsePipelineEntry(await requestPipeline(`/api/pipeline/${encodeURIComponent(entry.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "If-Match": `"${entry.version}"`, "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ stage }) })); setEntries((all) => all.map((item) => item.id === entry.id ? updated : item)) }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível alterar a etapa.") }
    finally { inFlight.current.delete(entry.id); setSaving([...inFlight.current]) }
  }

  if (!entries.length && !error) return <section className="kiara-copilot-stage kiara-soft-panel grid min-h-[440px] place-items-center p-8 text-center"><div><KiaraOrb size="lg" active /><h2 className="kiara-editorial mt-8 text-4xl">Sua fila começa com um bom alvo.</h2><p className="mx-auto mt-3 max-w-md text-muted-foreground">Encontre e valide leads no Hunter. Eu organizo o próximo movimento aqui.</p><Button asChild size="lg" className="mt-7 rounded-full"><Link href="/app/hunter">Abrir Hunter<ArrowRight /></Link></Button></div></section>

  return <section className="overflow-hidden rounded-[28px] border bg-card shadow-[var(--shadow-2)]">
    <header className="flex flex-col gap-4 border-b p-5 sm:p-6 xl:flex-row xl:items-center xl:justify-between"><div><p className="flex items-center gap-2 text-xs font-semibold text-primary"><Sparkles className="size-4" />Fila guiada pela Kiara</p><p className="mt-1 text-sm text-muted-foreground">{visible.length} contatos · escolha um para continuar</p></div><div className="flex flex-wrap gap-2"><div className="relative min-w-56 flex-1"><Search className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 bg-background pl-9" placeholder="Buscar na fila" /></div><Button variant="outline" onClick={() => void refresh()} disabled={loading}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}Atualizar</Button><Button asChild><Link href="/app/hunter"><Plus />Novo alvo</Link></Button></div></header>
    {error && <div role="alert" className="m-5 rounded-xl bg-destructive/8 p-4 text-sm text-destructive">{error}</div>}
    <div className="flex gap-2 overflow-x-auto border-b px-5 py-3">{[{ id: "all" as const, label: "Todos" }, ...pipelineStages].map((stage) => <button key={stage.id} onClick={() => setStageFilter(stage.id)} className={cn("shrink-0 rounded-full px-3 py-1.5 text-xs transition", stageFilter === stage.id ? "bg-foreground text-background" : "text-muted-foreground hover:bg-muted")}>{stage.label}</button>)}</div>
    <div className="grid min-h-[650px] min-w-0 lg:grid-cols-[240px_minmax(0,1fr)] 2xl:grid-cols-[260px_minmax(0,1fr)_280px]">
      <aside className="border-b bg-muted/25 p-3 lg:border-b-0 lg:border-r"><p className="px-3 py-2 text-xs font-semibold text-muted-foreground">Sua fila</p><div className="max-h-[600px] space-y-1 overflow-auto">{visible.map((entry) => <button key={entry.id} onClick={() => setSelectedId(entry.id)} className={cn("w-full rounded-2xl p-3 text-left transition", selected?.id === entry.id ? "bg-card shadow-sm ring-1 ring-primary/15" : "hover:bg-card/70")}><div className="flex gap-3"><span className={cn("mt-1.5 size-2.5 shrink-0 rounded-full", colors[entry.stage])} /><div className="min-w-0"><p className="truncate text-sm font-semibold">{entry.consumer.display_name}</p><p className="mt-1 truncate text-xs text-muted-foreground">{entry.next_action || "Revisar oportunidade"}</p><div className="mt-2 flex gap-2 text-muted-foreground">{entry.consumer.phone && <MessageCircle className="size-3.5" />}{entry.consumer.instagram_username && <AtSign className="size-3.5" />}</div></div></div></button>)}</div></aside>
      {selected && <main className="kiara-copilot-stage min-w-0 overflow-hidden flex flex-col items-center justify-center border-b px-5 py-10 text-center lg:border-b-0 2xl:border-r"><KiaraOrb size="lg" active /><p className="mt-7 text-xs font-semibold uppercase tracking-[.16em] text-primary">O que fazemos agora?</p><h2 className="kiara-editorial mt-3 max-w-xl break-words text-3xl leading-tight xl:text-4xl">{selected.next_action || `Vamos conhecer ${selected.consumer.display_name}?`}</h2><p className="mt-4 max-w-md text-sm leading-6 text-muted-foreground">Revise os sinais públicos, escolha o estágio e abra o WhatsApp somente quando estiver pronto.</p><div className="mt-7"><LeadContactActions entry={selected} onRecorded={refresh} /></div><Button asChild variant="ghost" className="mt-3 2xl:hidden"><Link href={`/app/leads/${encodeURIComponent(selected.consumer.id)}`}>Ver dossiê completo<ArrowRight /></Link></Button><div className="mt-8 flex max-w-xl flex-wrap justify-center gap-1.5">{pipelineStages.map((stage, index) => <button key={stage.id} disabled={saving.includes(selected.id)} onClick={() => void move(selected, stage.id)} className={cn("rounded-full px-3 py-2 text-[11px] font-medium transition", stage.id === selected.stage ? "bg-primary text-primary-foreground shadow-md" : index <= pipelineStages.findIndex((item) => item.id === selected.stage) ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground hover:text-foreground")}>{stage.label}</button>)}</div></main>}
      {selected && <aside className="hidden min-w-0 overflow-hidden p-6 2xl:block"><div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold text-muted-foreground">Dossiê do lead</p><Button asChild variant="ghost" size="sm"><Link href={`/app/leads/${encodeURIComponent(selected.consumer.id)}`}>Abrir<ArrowRight /></Link></Button></div><h3 className="kiara-editorial mt-6 break-words text-2xl leading-tight [overflow-wrap:anywhere]">{selected.consumer.display_name}</h3>{selected.consumer.address && <p className="mt-3 flex gap-2 break-words text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]"><MapPin className="mt-0.5 size-3.5 shrink-0" />{selected.consumer.address}</p>}<dl className="mt-8 min-w-0 space-y-5"><Fact icon={<MessageCircle />} label="Contato" value={selected.consumer.phone || "Não encontrado"} /><Fact icon={<Globe2 />} label="Presença digital" value={websiteLabel(selected.consumer.website_status)} /><Fact icon={<Sparkles />} label="Origem" value={sourceLabels[selected.consumer.source ?? ""] ?? "CRM"} />{selected.next_action_at && <Fact icon={<Clock3 />} label="Próxima ação" value={new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(selected.next_action_at))} />}</dl></aside>}
    </div>
  </section>
}

function Fact({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="flex min-w-0 gap-3 [&_svg]:mt-0.5 [&_svg]:size-4 [&_svg]:text-primary"><span className="shrink-0">{icon}</span><div className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-sm font-medium [overflow-wrap:anywhere]">{value}</dd></div></div> }
