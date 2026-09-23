"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, AtSign as Instagram, Check, ChevronDown, CircleDollarSign, Clock3, ExternalLink, Filter, Loader2, MapPin, MessageCircle, Phone, RefreshCw, Search, SlidersHorizontal, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { leadDisplayName, parsePipeline, PipelineRequestError, pipelineStages, requestPipeline, type PipelineEntry, type PipelineStage, websiteLabel } from "@/lib/api/pipeline"
import { cn } from "@/lib/utils"

const stageTheme: Record<PipelineStage, { dot: string; text: string; border: string; glow: string }> = {
  new: { dot: "bg-sky-400", text: "text-sky-300", border: "border-sky-400/30", glow: "shadow-sky-500/10" },
  qualified: { dot: "bg-violet-400", text: "text-violet-300", border: "border-violet-400/30", glow: "shadow-violet-500/10" },
  contacted: { dot: "bg-amber-400", text: "text-amber-300", border: "border-amber-400/30", glow: "shadow-amber-500/10" },
  opportunity: { dot: "bg-fuchsia-400", text: "text-fuchsia-300", border: "border-fuchsia-400/30", glow: "shadow-fuchsia-500/10" },
  won: { dot: "bg-emerald-400", text: "text-emerald-300", border: "border-emerald-400/30", glow: "shadow-emerald-500/10" },
  lost: { dot: "bg-rose-400", text: "text-rose-300", border: "border-rose-400/30", glow: "shadow-rose-500/10" },
}

type SortOrder = "name-asc" | "name-desc" | "recent" | "oldest"

const leadNameCollator = new Intl.Collator("pt-BR", { sensitivity: "base", numeric: true })

function initials(name: string) { const parts = name.replace(/^@/, "").split(/\s+/).filter(Boolean); return ((parts[0]?.[0] ?? "K") + (parts[1]?.[0] ?? "")).toUpperCase() }
function formatDate(value?: string | null) { return !value || Number.isNaN(Date.parse(value)) ? "Sem data" : new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" }).format(new Date(value)) }
function sourceCode(source?: string | null) { return source === "instagram" ? "IG" : source === "facebook" ? "FB" : source === "google_maps" ? "GM" : "WEB" }

export function PipelineBoard({ initialEntries }: { initialEntries: PipelineEntry[] }) {
  const [entries, setEntries] = useState(initialEntries)
  const [selectedId, setSelectedId] = useState(initialEntries[0]?.id ?? "")
  const [query, setQuery] = useState("")
  const [stageFilter, setStageFilter] = useState<PipelineStage | "all">("all")
  const [sortOrder, setSortOrder] = useState<SortOrder>("recent")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const selected = entries.find((entry) => entry.id === selectedId) ?? null
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("pt-BR")
    const matches = entries.filter((entry) => (stageFilter === "all" || entry.stage === stageFilter) && (!needle || `${leadDisplayName(entry.consumer)} ${entry.consumer.research_query ?? ""} ${entry.consumer.address ?? ""} ${entry.consumer.source ?? ""}`.toLocaleLowerCase("pt-BR").includes(needle)))
    return matches.sort((left, right) => {
      if (sortOrder === "name-asc") return leadNameCollator.compare(leadDisplayName(left.consumer), leadDisplayName(right.consumer))
      if (sortOrder === "name-desc") return leadNameCollator.compare(leadDisplayName(right.consumer), leadDisplayName(left.consumer))
      const leftTime = Date.parse(left.updated_at) || 0
      const rightTime = Date.parse(right.updated_at) || 0
      return sortOrder === "oldest" ? leftTime - rightTime : rightTime - leftTime
    })
  }, [entries, query, sortOrder, stageFilter])
  const counts = useMemo(() => Object.fromEntries(pipelineStages.map((stage) => [stage.id, entries.filter((entry) => entry.stage === stage.id).length])) as Record<PipelineStage, number>, [entries])

  async function refresh() { setLoading(true); setError(""); try { const next = parsePipeline(await requestPipeline("/api/pipeline")); setEntries(next); setSelectedId((current) => next.some((entry) => entry.id === current) ? current : next[0]?.id ?? "") } catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível atualizar o Pipeline.") } finally { setLoading(false) } }
  async function updateSelected(changes: { stage?: PipelineStage; next_action?: string | null }) {
    if (!selected) return
    setSaving(true); setError(""); setNotice("")
    try {
      const save = (entry: PipelineEntry) => requestPipeline(`/api/pipeline/${encodeURIComponent(entry.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "X-Kiara-Version": `"${entry.version}"`, "Idempotency-Key": `pipeline-${entry.id}-${Date.now()}` }, body: JSON.stringify(changes) })
      let saved: unknown
      try {
        saved = await save(selected)
      } catch (caught) {
        if (!(caught instanceof PipelineRequestError) || caught.status !== 412) throw caught
        const latestEntries = parsePipeline(await requestPipeline("/api/pipeline"))
        const latest = latestEntries.find((entry) => entry.id === selected.id)
        if (!latest) throw new Error("Este lead não está mais disponível no Pipeline.")
        setEntries(latestEntries)
        saved = await save(latest)
      }
      const updated = parsePipeline({ items: [saved] })[0]
      setEntries((current) => current.map((entry) => entry.id === updated.id ? updated : entry)); setNotice("Alterações salvas.")
    } catch (caught) {
      if (caught instanceof PipelineRequestError && caught.status === 412) {
        try {
          const latestEntries = parsePipeline(await requestPipeline("/api/pipeline"))
          setEntries(latestEntries)
          setSelectedId((current) => latestEntries.some((entry) => entry.id === current) ? current : latestEntries[0]?.id ?? "")
        } catch { /* O conflito já foi reconciliado; uma atualização manual continua disponível. */ }
        return
      }
      setError(caught instanceof Error ? caught.message : "Não foi possível atualizar o Pipeline.")
    } finally { setSaving(false) }
  }

  return <div className="mx-auto w-full max-w-[1680px] space-y-3">
    <section aria-label="Resumo do pipeline" className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">{pipelineStages.map((stage) => { const theme = stageTheme[stage.id]; return <button key={stage.id} type="button" onClick={() => setStageFilter((current) => current === stage.id ? "all" : stage.id)} className={cn("group rounded-xl border bg-card/80 px-3 py-2.5 text-left shadow-lg backdrop-blur transition hover:-translate-y-0.5", theme.border, theme.glow, stageFilter === stage.id && "ring-1 ring-primary/70")}><span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground"><span className={cn("size-1.5 rounded-full shadow-[0_0_8px_currentColor]", theme.dot)} />{stage.label}</span><span className="mt-1 flex items-end justify-between"><strong className="text-xl leading-none tabular-nums">{counts[stage.id]}</strong><small className={cn("text-[9px] font-semibold", theme.text)}>{stage.id === "won" ? "concluídos" : "no fluxo"}</small></span></button> })}</section>
    <div className="flex flex-col gap-2 rounded-xl border bg-card/70 p-2 backdrop-blur md:flex-row md:items-center"><div className="flex flex-wrap gap-1.5"><button type="button" onClick={() => setStageFilter("all")} className={cn("rounded-lg border px-3 py-1.5 text-xs font-semibold", stageFilter === "all" ? "border-primary/60 bg-primary/15 text-primary" : "border-border bg-background/50 text-muted-foreground")}>Todos</button>{pipelineStages.slice(0, 5).map((stage) => <button key={stage.id} type="button" onClick={() => setStageFilter(stage.id)} className={cn("rounded-lg border px-3 py-1.5 text-xs", stageFilter === stage.id ? "border-primary/60 bg-primary/15 text-primary" : "border-border bg-background/50 text-muted-foreground")}>{stage.label}</button>)}</div><div className="relative min-w-0 flex-1 md:ml-auto md:max-w-xs"><Search className="absolute left-3 top-2.5 size-3.5 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-8 rounded-lg bg-background/60 pl-8 text-xs" placeholder="Buscar lead..." aria-label="Buscar leads no Pipeline" /></div><Button size="sm" variant="outline" className="h-8" onClick={() => void refresh()} disabled={loading}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}Atualizar</Button></div>
    {error && <div role="alert" className="flex items-start gap-3 rounded-xl border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive"><TriangleAlert className="mt-0.5 size-4 shrink-0" />{error}</div>}
    {notice && <div role="status" className="flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-3 text-sm text-emerald-300"><Check className="size-4" />{notice}</div>}
    {!entries.length ? <EmptyPipeline /> : <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]"><section className="min-w-0 overflow-hidden rounded-xl border bg-card/80" aria-label="Leads do pipeline"><header className="grid grid-cols-[minmax(0,1fr)_40px] items-center gap-3 border-b bg-muted/20 px-4 py-2 text-[10px] font-semibold uppercase tracking-[.13em] text-muted-foreground"><span>Lead</span><DropdownMenu><DropdownMenuTrigger asChild><button type="button" className="ml-auto grid size-8 place-items-center rounded-lg text-muted-foreground transition hover:bg-primary/10 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Ordenar leads"><SlidersHorizontal className="size-3.5" /></button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-52"><DropdownMenuLabel>Ordenar leads</DropdownMenuLabel><DropdownMenuRadioGroup value={sortOrder} onValueChange={(value) => setSortOrder(value as SortOrder)}><DropdownMenuRadioItem value="name-asc">Ordem crescente</DropdownMenuRadioItem><DropdownMenuRadioItem value="name-desc">Ordem decrescente</DropdownMenuRadioItem><DropdownMenuRadioItem value="recent">Mais recentes</DropdownMenuRadioItem><DropdownMenuRadioItem value="oldest">Mais antigos</DropdownMenuRadioItem></DropdownMenuRadioGroup></DropdownMenuContent></DropdownMenu></header><div className="max-h-[640px] overflow-y-auto overscroll-contain">{filtered.length ? <ul className="relative before:absolute before:bottom-0 before:left-[25px] before:top-0 before:w-px before:bg-border/80">{filtered.map((entry) => <PipelineRow key={entry.id} entry={entry} active={entry.id === selectedId} onSelect={() => { setSelectedId(entry.id); setNotice("") }} />)}</ul> : <div className="grid min-h-52 place-items-center p-8 text-center"><div><Filter className="mx-auto size-5 text-primary" /><p className="mt-3 text-sm font-semibold">Nenhum lead encontrado</p><p className="mt-1 text-xs text-muted-foreground">Ajuste a busca ou limpe o filtro atual.</p></div></div>}</div></section><PipelineInspector key={selected?.id ?? "empty"} entry={selected} saving={saving} onUpdate={updateSelected} /></div>}
  </div>
}

function PipelineRow({ entry, active, onSelect }: { entry: PipelineEntry; active: boolean; onSelect: () => void }) {
  const name = leadDisplayName(entry.consumer); const stage = pipelineStages.find((item) => item.id === entry.stage)!; const theme = stageTheme[entry.stage]
  return <li className="relative border-b last:border-b-0"><button type="button" onClick={onSelect} className={cn("grid w-full grid-cols-[36px_minmax(0,1fr)_40px] items-center gap-3 px-3 py-2.5 text-left transition hover:bg-primary/[.045]", active && "bg-primary/[.09] before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-primary")}><span className={cn("relative z-10 grid size-7 place-items-center rounded-full border bg-[#17152b] text-[9px] font-bold", theme.border, theme.text)}>{initials(name)}</span><span className="min-w-0"><strong className="block truncate text-xs font-semibold">{name}</strong><span className="mt-1 flex min-w-0 items-center gap-1.5"><span className="rounded border border-border/70 bg-background/50 px-1.5 py-0.5 text-[8px] font-bold text-muted-foreground">{sourceCode(entry.consumer.source)}</span><span className={cn("inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[8px] font-semibold", theme.border, theme.text)}><span className={cn("size-1 rounded-full", theme.dot)} />{stage.label}</span><span className="truncate text-[9px] text-muted-foreground">{entry.consumer.address || websiteLabel(entry.consumer.website_status)}</span></span></span><ArrowRight className={cn("ml-auto size-3.5 text-muted-foreground", active && "text-primary")} /></button></li>
}

function PipelineInspector({ entry, saving, onUpdate }: { entry: PipelineEntry | null; saving: boolean; onUpdate: (changes: { stage?: PipelineStage; next_action?: string | null }) => Promise<void> }) {
  const [stage, setStage] = useState<PipelineStage>(entry?.stage ?? "new"); const [nextAction, setNextAction] = useState(entry?.next_action ?? "")
  if (!entry) return <aside className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">Selecione um lead para ver os detalhes.</aside>
  const name = leadDisplayName(entry.consumer); const theme = stageTheme[entry.stage]
  return <aside className="h-fit overflow-hidden rounded-xl border bg-card/90 shadow-2xl shadow-black/20 xl:sticky xl:top-3"><div className="border-b bg-gradient-to-br from-primary/[.14] via-transparent to-transparent p-4"><div className="flex items-start gap-3"><span className={cn("grid size-10 shrink-0 place-items-center rounded-full border bg-primary/15 text-xs font-bold", theme.border, theme.text)}>{initials(name)}</span><span className="min-w-0 flex-1"><h2 className="truncate text-sm font-bold">{name}</h2><p className="mt-1 flex items-center gap-1 truncate text-[10px] text-muted-foreground"><MapPin className="size-3 shrink-0" />{entry.consumer.address || "Localização não informada"}</p></span><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} aria-label={`Abrir ficha de ${name}`} className="rounded-lg border p-2 text-muted-foreground hover:border-primary/50 hover:text-primary"><ExternalLink className="size-3.5" /></Link></div><div className="mt-3 grid grid-cols-3 gap-1.5"><ContactBadge icon={Phone} enabled={Boolean(entry.consumer.phone)} label="Telefone" /><ContactBadge icon={MessageCircle} enabled={Boolean(entry.consumer.whatsapp_url)} label="WhatsApp" /><ContactBadge icon={Instagram} enabled={Boolean(entry.consumer.instagram_username)} label="Instagram" /></div></div><div className="space-y-3 p-4"><div><label htmlFor="pipeline-stage" className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground">Etapa do pipeline</label><div className="relative"><select id="pipeline-stage" value={stage} onChange={(event) => setStage(event.target.value as PipelineStage)} className="h-9 w-full appearance-none rounded-lg border bg-background/70 px-3 pr-8 text-xs outline-none focus:border-primary">{pipelineStages.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-2.5 size-3.5 text-muted-foreground" /></div></div><div><label htmlFor="pipeline-next-action" className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground">Próxima ação</label><Input id="pipeline-next-action" value={nextAction} onChange={(event) => setNextAction(event.target.value)} className="h-9 text-xs" placeholder="Ex.: Enviar proposta amanhã" /></div><Button className="h-9 w-full" disabled={saving} onClick={() => void onUpdate({ stage, next_action: nextAction.trim() || null })}>{saving ? <Loader2 className="animate-spin" /> : <Check />}Salvar avanço</Button><Button asChild variant="outline" className="h-9 w-full"><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`}>Ver ficha completa<ArrowRight /></Link></Button><div><p className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground"><Clock3 className="size-3" />Histórico recente</p><div className="space-y-2 border-l border-border pl-3">{entry.activities?.slice(0, 3).map((activity) => <div key={activity.id} className="relative text-[10px] before:absolute before:-left-[15px] before:top-1 before:size-1 before:rounded-full before:bg-primary"><p className="font-medium">{activity.status === "sent" ? "Contato registrado" : "Atividade criada"}</p><time className="text-muted-foreground">{formatDate(activity.created_at)}</time></div>)}{!entry.activities?.length && <p className="relative text-[10px] text-muted-foreground before:absolute before:-left-[15px] before:top-1 before:size-1 before:rounded-full before:bg-muted-foreground">Nenhuma atividade registrada.</p>}</div></div></div></aside>
}

function ContactBadge({ icon: Icon, enabled, label }: { icon: typeof Phone; enabled: boolean; label: string }) { return <span title={label} className={cn("flex items-center justify-center gap-1 rounded-lg border px-2 py-1.5 text-[9px]", enabled ? "border-primary/25 bg-primary/10 text-primary" : "border-border/70 text-muted-foreground/60")}><Icon className="size-3" />{label}</span> }
function EmptyPipeline() { return <div className="grid min-h-72 place-items-center rounded-xl border border-dashed bg-card/50 p-8 text-center"><div><CircleDollarSign className="mx-auto size-7 text-primary" /><h2 className="mt-3 text-lg font-semibold">Seu Pipeline começa com uma pesquisa</h2><p className="mt-2 text-sm text-muted-foreground">Encontre leads no Hunter e organize cada oportunidade aqui.</p><Button asChild className="mt-5"><Link href="/app/hunter">Pesquisar leads<ArrowRight /></Link></Button></div></div> }
