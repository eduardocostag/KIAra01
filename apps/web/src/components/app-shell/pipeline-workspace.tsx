"use client"

import Link from "next/link"
import { useRef, useState } from "react"
import { Columns3, Loader2, Plus, RefreshCw, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { LeadContactActions } from "./lead-contact-actions"
import { parsePipeline, parsePipelineEntry, pipelineStages, requestPipeline, sourceLabels, type PipelineEntry, type PipelineStage } from "@/lib/api/pipeline"

export function PipelineWorkspace({ initialEntries, initialError = "" }: { initialEntries: PipelineEntry[]; initialError?: string }) {
  const [entries, setEntries] = useState(initialEntries)
  const [error, setError] = useState(initialError)
  const [notice, setNotice] = useState("")
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState<string[]>([])
  const inFlight = useRef(new Set<string>())
  const refreshing = useRef(false)
  const visible = entries.filter((entry) => `${entry.consumer.display_name} ${entry.consumer.phone ?? ""} ${entry.consumer.research_query ?? ""}`.toLocaleLowerCase("pt-BR").includes(query.toLocaleLowerCase("pt-BR")))

  async function refresh() {
    if (refreshing.current || inFlight.current.size) return
    refreshing.current = true
    setLoading(true)
    setError("")
    try { setEntries(parsePipeline(await requestPipeline("/api/pipeline"))) }
    catch (error) { setError(error instanceof Error ? error.message : "Não foi possível atualizar o Pipeline.") }
    finally { refreshing.current = false; setLoading(false) }
  }

  async function move(entry: PipelineEntry, stage: PipelineStage) {
    if (stage === entry.stage || inFlight.current.has(entry.id) || refreshing.current) return
    inFlight.current.add(entry.id)
    setSaving([...inFlight.current])
    setError("")
    setNotice("")
    try {
      const updated = parsePipelineEntry(await requestPipeline(`/api/pipeline/${encodeURIComponent(entry.id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json", "If-Match": `"${entry.version}"`, "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ stage }),
      }))
      setEntries((current) => current.map((item) => item.id === entry.id ? updated : item))
      setNotice(`${entry.consumer.display_name}: etapa atualizada para ${pipelineStages.find((item) => item.id === stage)?.label}.`)
    } catch (error) { setError(error instanceof Error ? error.message : "Não foi possível alterar a etapa. Atualize antes de repetir.") }
    finally { inFlight.current.delete(entry.id); setSaving([...inFlight.current]) }
  }

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-48 flex-1"><Search className="absolute top-3 left-3 size-4 text-muted-foreground" /><Input className="h-10 pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nome, contato ou pesquisa" aria-label="Buscar no Pipeline" /></div>
      <span className="text-sm text-muted-foreground">{entries.length} leads</span>
      <Button variant="outline" disabled={loading || saving.length > 0} onClick={refresh}>{loading ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}Atualizar</Button>
      <Button asChild><Link href="/app/hunter"><Plus />Buscar leads</Link></Button>
    </div>
    {error && <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>}
    <p className="sr-only" role="status">{notice}</p>
    {!entries.length && !error ? <div className="grid min-h-72 place-items-center rounded-xl border border-dashed bg-card p-8 text-center"><div><Columns3 className="mx-auto size-7 text-muted-foreground" /><h2 className="mt-4 font-semibold">Seu próximo lead começa no Hunter</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">Novas pesquisas adicionam os leads aprovados pelos filtros aqui. Pesquisas antigas sem validação permanecem apenas no histórico.</p><Button asChild className="mt-5"><Link href="/app/hunter">Criar pesquisa</Link></Button></div></div> : <>
      {query && !visible.length && <p role="status" className="py-6 text-center text-sm text-muted-foreground">Nenhum lead corresponde a essa busca.</p>}
      <div className="grid min-w-0 gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {pipelineStages.map((stage) => {
          const items = visible.filter((entry) => entry.stage === stage.id)
          return <section key={stage.id} aria-label={`Etapa ${stage.label}`} className="min-w-0 rounded-xl border bg-muted/35 p-3">
            <header className="mb-3 flex items-center justify-between px-1 py-1"><div><h2 className="text-sm font-semibold">{stage.label}</h2><p className="mt-0.5 text-xs text-muted-foreground">{stage.description}</p></div><span className="min-w-7 rounded-md border bg-card px-2 py-1 text-center text-xs tabular-nums">{items.length}</span></header>
            <div className="space-y-3">{items.length ? items.map((entry) => <article key={entry.id} className="min-w-0 rounded-lg border bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{sourceLabels[entry.consumer.source ?? ""] ?? "CRM"}</p>
              <Link className="block break-words font-semibold leading-5 hover:text-primary" href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`}>{entry.consumer.display_name}</Link>
              {entry.consumer.instagram_username && <p className="mt-1 text-xs text-muted-foreground">@{entry.consumer.instagram_username}</p>}
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{entry.next_action || "Revisar contato e definir próxima ação."}</p>
              <div className="mt-3"><LeadContactActions consumer={entry.consumer} /></div>
              <div className="mt-4 border-t pt-3"><Select disabled={loading || saving.includes(entry.id)} value={entry.stage} onValueChange={(value) => void move(entry, value as PipelineStage)}><SelectTrigger className="h-9 w-full text-xs" aria-label={`Etapa de ${entry.consumer.display_name}`}><SelectValue /></SelectTrigger><SelectContent>{pipelineStages.map((item) => <SelectItem key={item.id} value={item.id}>{item.label}</SelectItem>)}</SelectContent></Select></div>
            </article>) : <p className="py-7 text-center text-xs text-muted-foreground">Nenhum lead nesta etapa</p>}</div>
          </section>
        })}
      </div>
    </>}
  </div>
}
