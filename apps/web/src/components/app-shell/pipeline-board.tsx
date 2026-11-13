"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { ArrowRight, AtSign, Check, Loader2, MapPin, MessageCircle, Phone, RefreshCw, Search, TriangleAlert, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { PipelineFunnel } from "./pipeline-funnel"
import { burst } from "@/components/fx/fx"
import { temperatureLabels } from "@/lib/api/inbox-contract"
import { instagramProfileUrl, leadDisplayName, parsePipeline, phoneHref, PipelineRequestError, pipelineStages, requestPipeline, type PipelineEntry, type PipelineStage, whatsappComposerUrl } from "@/lib/api/pipeline"
import { cn } from "@/lib/utils"

const WHATSAPP_MESSAGE = "Olá, {nome}! Tudo bem? Encontrei seu contato durante uma pesquisa comercial e gostaria de conversar brevemente sobre uma possível oportunidade. Podemos falar?"

const stageDot: Record<PipelineStage, string> = {
  new: "bg-sky-400",
  qualified: "bg-violet-400",
  contacted: "bg-amber-400",
  opportunity: "bg-fuchsia-400",
  won: "bg-emerald-400",
  lost: "bg-rose-400",
}

type Changes = { stage?: PipelineStage; next_action?: string | null; notes?: string | null }

function stageLabel(stage: PipelineStage) {
  return pipelineStages.find((item) => item.id === stage)?.label ?? stage
}

function initials(name: string) {
  const parts = name.replace(/^@/, "").split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? "K") + (parts[1]?.[0] ?? "")).toUpperCase()
}

export function PipelineBoard({ entries, onEntriesChange, initialSelectedId = "" }: {
  entries: PipelineEntry[]
  onEntriesChange: (entries: PipelineEntry[]) => void
  initialSelectedId?: string
}) {
  const [selectedId, setSelectedId] = useState(initialSelectedId || entries[0]?.id || "")
  const [query, setQuery] = useState("")
  const [stageFilter, setStageFilter] = useState<PipelineStage | "active">(() => {
    const requested = entries.find((entry) => entry.id === initialSelectedId)
    return requested?.stage === "won" || requested?.stage === "lost" ? requested.stage : "active"
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  const counts = useMemo(() => Object.fromEntries(pipelineStages.map((stage) => [stage.id, entries.filter((entry) => entry.stage === stage.id).length])) as Record<PipelineStage, number>, [entries])
  const activeCount = entries.length - counts.won - counts.lost
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("pt-BR")
    return entries
      .filter((entry) => stageFilter === "active" ? entry.stage !== "won" && entry.stage !== "lost" : entry.stage === stageFilter)
      .filter((entry) => !needle || `${leadDisplayName(entry.consumer)} ${entry.consumer.phone ?? ""} ${entry.consumer.address ?? ""}`.toLocaleLowerCase("pt-BR").includes(needle))
      .sort((left, right) => (Date.parse(right.updated_at) || 0) - (Date.parse(left.updated_at) || 0))
  }, [entries, query, stageFilter])
  const selected = filtered.find((entry) => entry.id === selectedId) ?? filtered[0] ?? null

  function replace(next: PipelineEntry[]) {
    onEntriesChange(next)
    setSelectedId((current) => next.some((entry) => entry.id === current) ? current : next[0]?.id ?? "")
  }

  async function refresh() {
    setLoading(true); setError("")
    try { replace(parsePipeline(await requestPipeline("/api/pipeline"))) }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Não foi possível atualizar os contatos.") }
    finally { setLoading(false) }
  }

  async function save(changes: Changes) {
    if (!selected) return
    setSaving(true); setError(""); setNotice("")
    const send = (entry: PipelineEntry) => requestPipeline(`/api/pipeline/${encodeURIComponent(entry.id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-Kiara-Version": `"${entry.version}"`, "Idempotency-Key": `pipeline-${entry.id}-${Date.now()}` },
      body: JSON.stringify(changes),
    })
    try {
      let base = entries
      let saved: unknown
      try {
        saved = await send(selected)
      } catch (caught) {
        // Someone else changed this lead: reload it and apply the edit on the latest version once.
        if (!(caught instanceof PipelineRequestError) || caught.status !== 412) throw caught
        base = parsePipeline(await requestPipeline("/api/pipeline"))
        const latest = base.find((entry) => entry.id === selected.id)
        if (!latest) { onEntriesChange(base); throw new Error("Este contato não está mais disponível.") }
        saved = await send(latest)
      }
      const updated = parsePipeline({ items: [saved] })[0]
      onEntriesChange(base.map((entry) => entry.id === updated.id ? updated : entry))
      setNotice(updated.stage === "won" && selected.stage !== "won" ? "Negócio fechado! 🎉" : "Salvo.")
      if (updated.stage === "won" && selected.stage !== "won") burst(document.querySelector<HTMLElement>("aside[aria-label^='Contato']"), "#34d399", 32)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Não foi possível salvar.")
    } finally { setSaving(false) }
  }

  if (!entries.length) return <EmptyContacts />

  const filters: { id: PipelineStage | "active"; label: string; count: number }[] = [
    { id: "active", label: "Em andamento", count: activeCount },
    ...pipelineStages.map((stage) => ({ id: stage.id, label: stage.label, count: counts[stage.id] })),
  ]

  return <div className="space-y-4">
    <PipelineFunnel counts={counts} active={stageFilter} onPick={(stage) => setStageFilter((current) => current === stage ? "active" : stage)} />
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <div className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] lg:mx-0 lg:flex-wrap lg:px-0" role="group" aria-label="Filtrar por etapa">
        {filters.map((filter) => <button key={filter.id} type="button" aria-pressed={stageFilter === filter.id} onClick={() => setStageFilter(filter.id)} className={cn("inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition", stageFilter === filter.id ? "border-primary/50 bg-primary/15 text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
          {filter.id !== "active" && <span className={cn("size-1.5 rounded-full", stageDot[filter.id])} aria-hidden="true" />}
          {filter.label}<span className="tabular-nums text-muted-foreground">{filter.count}</span>
        </button>)}
      </div>
      <div className="flex gap-2 lg:ml-auto">
        <div className="relative min-w-0 flex-1 lg:w-64">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 pl-9" placeholder="Buscar nome ou telefone" aria-label="Buscar contatos" />
        </div>
        <Button variant="outline" size="icon" className="size-10 shrink-0" aria-label="Atualizar contatos" onClick={() => void refresh()} disabled={loading}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}</Button>
      </div>
    </div>

    {error && <p role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"><TriangleAlert className="mt-0.5 size-4 shrink-0" />{error}</p>}

    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
      <section aria-label="Contatos" className="min-w-0 overflow-hidden rounded-xl border bg-card">
        {filtered.length ? <ul className="max-h-[680px] divide-y overflow-y-auto">
          {filtered.map((entry, index) => {
            const name = leadDisplayName(entry.consumer)
            const active = entry.id === selected?.id
            return <li key={entry.id} className="fx-rise fx-spot" style={{ "--i": index } as React.CSSProperties}><button type="button" aria-current={active ? "true" : undefined} onClick={() => { setSelectedId(entry.id); setNotice("") }} className={cn("flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-muted/40", active && "bg-primary/10")}>
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">{initials(name)}</span>
              <span className="min-w-0 flex-1">
                <span className="flex min-w-0 items-center gap-2"><span className="truncate text-sm font-medium">{name}</span>{entry.consumer.fit ? <FitChip fit={entry.consumer.fit} /> : null}</span>
                <span className="block truncate text-xs text-muted-foreground">{entry.next_action || entry.consumer.phone || entry.consumer.address || "Sem contato informado"}</span>
              </span>
              <span className="hidden shrink-0 items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex"><span className={cn("size-1.5 rounded-full", stageDot[entry.stage])} aria-hidden="true" />{stageLabel(entry.stage)}</span>
            </button></li>
          })}
        </ul> : <p className="p-8 text-center text-sm text-muted-foreground">Nenhum contato nesta etapa{query ? " com essa busca" : ""}.</p>}
      </section>
      {selected ? <ContactPanel key={`${selected.id}-${selected.version}`} entry={selected} saving={saving} notice={notice} onSave={save} /> : null}
    </div>
  </div>
}

const fitChipStyles = { A: "bg-emerald-400/15 text-emerald-300", B: "bg-sky-400/15 text-sky-300", C: "bg-amber-400/15 text-amber-300", D: "bg-muted text-muted-foreground" } as const

/** Lead fit grade from the API; the full explanation lives on the lead page. */
function FitChip({ fit, detailed = false }: { fit: NonNullable<PipelineEntry["consumer"]["fit"]>; detailed?: boolean }) {
  return <span title={`${fit.label}: ${fit.score}/100`} aria-label={`Nota ${fit.grade}, ${fit.score} de 100`} className={cn("inline-flex shrink-0 items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold tabular-nums", fitChipStyles[fit.grade])}>{fit.grade}{detailed ? ` · ${fit.score}` : ""}</span>
}

function ContactPanel({ entry, saving, notice, onSave }: { entry: PipelineEntry; saving: boolean; notice: string; onSave: (changes: Changes) => Promise<void> }) {
  const [stage, setStage] = useState<PipelineStage>(entry.stage)
  const [nextAction, setNextAction] = useState(entry.next_action ?? "")
  const [notes, setNotes] = useState(entry.consumer.notes ?? "")
  const name = leadDisplayName(entry.consumer)
  const whatsapp = whatsappComposerUrl(entry.consumer.phone, entry.consumer.whatsapp_url, WHATSAPP_MESSAGE.replace("{nome}", name.replace(/^@/, "")))
  const telephone = phoneHref(entry.consumer.phone)
  const instagram = instagramProfileUrl(entry.consumer.instagram_username)
  const qualification = entry.qualification
  const changed = stage !== entry.stage || nextAction.trim() !== (entry.next_action ?? "") || notes.trim() !== (entry.consumer.notes ?? "").trim()

  return <aside aria-label={`Contato ${name}`} className="fx-rise h-fit space-y-5 rounded-xl border bg-card p-5 lg:sticky lg:top-6">
    <header>
      <h2 className="flex items-center gap-2 text-lg font-semibold leading-tight">{name}{entry.consumer.fit ? <FitChip fit={entry.consumer.fit} detailed /> : null}</h2>
      <p className="mt-1 flex items-start gap-1.5 text-sm text-muted-foreground"><MapPin className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />{entry.consumer.address || "Localização não informada"}</p>
      {entry.consumer.phone && <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground"><Phone className="size-3.5 shrink-0" aria-hidden="true" />{entry.consumer.phone}</p>}
    </header>

    <div className="flex flex-wrap gap-2">
      {whatsapp ? <Button asChild size="sm"><a href={whatsapp.url} target="_blank" rel="noopener noreferrer"><MessageCircle />WhatsApp</a></Button> : null}
      {telephone ? <Button asChild size="sm" variant="outline"><a href={telephone}><Phone />Ligar</a></Button> : null}
      {instagram ? <Button asChild size="sm" variant="outline"><a href={instagram} target="_blank" rel="noopener noreferrer"><AtSign />Instagram</a></Button> : null}
      {!whatsapp && !telephone && !instagram ? <p className="text-sm text-muted-foreground">Nenhum canal de contato disponível.</p> : null}
    </div>

    {qualification ? <div className="rounded-lg bg-muted/40 p-3 text-sm">
      <p className="flex items-center justify-between font-medium"><span>{temperatureLabels[qualification.temperature] ?? "Não classificado"}</span><span className="tabular-nums text-muted-foreground">{qualification.score}/100</span></p>
      {qualification.recommendation ? <p className="mt-1 text-muted-foreground">{qualification.recommendation}</p> : null}
    </div> : null}

    <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (changed) void onSave({ stage, next_action: nextAction.trim() || null, notes: notes.trim() || null }) }}>
      <div className="space-y-1.5">
        <label htmlFor="contact-stage" className="text-sm font-medium">Etapa</label>
        <select id="contact-stage" value={stage} onChange={(event) => setStage(event.target.value as PipelineStage)} className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {pipelineStages.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </div>
      <div className="space-y-1.5">
        <label htmlFor="contact-next-action" className="text-sm font-medium">Próxima ação</label>
        <Input id="contact-next-action" value={nextAction} maxLength={300} onChange={(event) => setNextAction(event.target.value)} className="h-10" placeholder="Ex.: Enviar proposta amanhã" />
      </div>
      <div className="space-y-1.5">
        <label htmlFor="contact-notes" className="text-sm font-medium">Anotações</label>
        <Textarea id="contact-notes" value={notes} maxLength={5000} rows={4} onChange={(event) => setNotes(event.target.value)} placeholder="Preferências, contexto da conversa…" />
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving || !changed}>{saving ? <Loader2 className="animate-spin" /> : <Check />}Salvar</Button>
        {notice && !changed ? <span role="status" className="text-sm text-muted-foreground">{notice}</span> : null}
        <Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} className="ml-auto inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">Ficha completa<ArrowRight className="size-3.5" /></Link>
      </div>
    </form>
  </aside>
}

function EmptyContacts() {
  return <div className="grid min-h-64 place-items-center rounded-xl border border-dashed p-8 text-center">
    <div>
      <Users className="mx-auto size-6 text-muted-foreground" aria-hidden="true" />
      <h2 className="mt-3 font-semibold">Nenhum contato ainda</h2>
      <p className="mt-1 text-sm text-muted-foreground">Faça uma busca e adicione os leads que interessam.</p>
      <Button asChild className="mt-4"><Link href="/app/hunter">Buscar leads<ArrowRight /></Link></Button>
    </div>
  </div>
}
