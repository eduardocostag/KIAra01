"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import dynamic from "next/dynamic"
import { useRouter } from "next/navigation"
import { ChevronDown, Loader2, Map as MapIcon, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { HunterActivity } from "./hunter-activity"
import { HunterResults } from "./hunter-results"
import { inferredWebsiteFilter, parseHunterHistory, parseHunterJob, requestHunter, type ContactFilter, type WebsiteFilter, type HunterSource as Source, type HunterJob as Job } from "@/lib/api/hunter-client"
import { cn } from "@/lib/utils"
import { coordinatesFromMapsUrl } from "@/lib/lead-geo"
import type { MapLead } from "./lead-map-3d"

// MapLibre only loads on this page, after the form is interactive.
const LeadMap3D = dynamic(() => import("./lead-map-3d"), { ssr: false, loading: () => <div className="fx-skeleton h-[clamp(260px,46vh,460px)] rounded-2xl" /> })
const MAP_PREFERENCE = "kiara.hunter.map"

const sourceLabels: Record<Source, string> = { google_maps: "Google Maps", web: "Web", instagram: "Instagram", facebook: "Facebook" }
const websiteLabels: Record<WebsiteFilter, string> = { any: "Com ou sem site", without_website: "Sem site", with_website: "Com site" }
const contactLabels: Record<ContactFilter, string> = { any: "Telefone ou WhatsApp", phone: "Somente com telefone", whatsapp: "Somente com WhatsApp" }

const HUNTER_MAX_RESULTS = 100
const selectClass = "h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"

export function HunterClient() {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [location, setLocation] = useState("")
  const [limit, setLimit] = useState(30)
  const [sources, setSources] = useState<Source[]>(["google_maps", "web"])
  const [websiteFilter, setWebsiteFilter] = useState<WebsiteFilter>("any")
  const [contactFilter, setContactFilter] = useState<ContactFilter>("any")
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [jobs, setJobs] = useState<Job[]>([])
  const [clearReview, setClearReview] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState("Preparando a busca…")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showMap, setShowMap] = useState(() => {
    try { return typeof window === "undefined" || window.localStorage.getItem(MAP_PREFERENCE) !== "off" } catch { return true }
  })
  const [mapUnavailable, setMapUnavailable] = useState(false)
  const requestVersion = useRef(0)
  const inFlight = useRef(false)

  const processQueued = useCallback(async (id: string) => {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const current = parseHunterJob(await requestHunter(
        `/api/hunter/searches/${encodeURIComponent(id)}/process`, { method: "POST" }, 210_000,
      ))
      setJobs((items) => [current, ...items.filter((item) => item.id !== current.id)])
      if (current.status !== "running") return current
      setStage("Aguardando as fontes responderem…")
      await new Promise((resolve) => setTimeout(resolve, 15_000))
    }
    return parseHunterJob(await requestHunter(`/api/hunter/searches/${encodeURIComponent(id)}`))
  }, [])

  const load = useCallback(async () => {
    const version = ++requestVersion.current
    setLoading(true)
    try {
      const history = parseHunterHistory(await requestHunter("/api/hunter/searches"))
      if (version === requestVersion.current) { setJobs(history); setError("") }
    } catch (e) {
      if (version === requestVersion.current) setError(e instanceof Error ? e.message : "Falha ao carregar as buscas.")
    } finally { if (version === requestVersion.current) setLoading(false) }
  }, [])
  // Synchronize persisted history without allowing an old GET to replace a new search.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    // A search left running (closed tab, reload) is resumed when the page opens again.
    const running = jobs.find((job) => job.status === "running")
    if (!running || inFlight.current || loading) return
    inFlight.current = true
    setBusy(true); setStage("Retomando a busca salva…")
    void processQueued(running.id)
      .then(() => router.refresh())
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Não foi possível retomar a busca."))
      .finally(() => { inFlight.current = false; setBusy(false) })
  }, [jobs, loading, processQueued, router])

  const latest = jobs.find((job) => job.id === selectedId) ?? jobs[0]
  const mapLeads = useMemo<MapLead[]>(() => (latest?.status === "completed" ? latest.results : []).flatMap((result) => {
    const data = result.public_data
    const at = coordinatesFromMapsUrl(result.source === "google_maps" ? result.url : data?.source_url)
    return at ? [{ id: result.id, name: result.title, at, temperature: data?.temperature ?? "cold", score: data?.lead_score ?? null }] : []
  }), [latest])
  // The SDR module prospects businesses; only an explicit end-consumer target is B2C.
  const market = /\b(?:consumidor(?:es|a|as)?|pessoas? f[ií]sicas?|clientes? finais?)\b/i.test(query) ? "b2c" : "b2b"
  const inferredWebsite = inferredWebsiteFilter(query, "")
  const effectiveWebsite = inferredWebsite !== "any" ? inferredWebsite : websiteFilter
  const requiresMaps = effectiveWebsite === "without_website"
  const sourceSet = new Set<Source>(sources)
  if (requiresMaps) sourceSet.add("google_maps")
  if (/\b(?:instagram|insta|reels?)\b/i.test(query)) sourceSet.add("instagram")
  if (/\b(?:facebook|fb)\b/i.test(query)) sourceSet.add("facebook")
  const effectiveSources = [...sourceSet]
  const canSearch = query.trim().length >= 2 && effectiveSources.length > 0 && !busy
  const filterSummary = [effectiveSources.map((source) => sourceLabels[source]).join(", "), `até ${limit}`, websiteLabels[effectiveWebsite], contactLabels[contactFilter]].join(" · ")

  function toggle(source: Source) {
    if (source === "google_maps" && requiresMaps) return
    setSources((all) => all.includes(source) ? all.filter((item) => item !== source) : [...all, source])
  }
  function broaden(job: Job) {
    setQuery(job.query); setLocation(job.location || ""); setSources(job.sources)
    setWebsiteFilter("any"); setContactFilter("any")
    document.getElementById("hunter-query")?.focus()
  }
  async function search() {
    if (inFlight.current || !canSearch) return
    inFlight.current = true
    ++requestVersion.current
    setLoading(false); setStage("Registrando a busca…"); setBusy(true); setError("")
    try {
      const job = parseHunterJob(await requestHunter("/api/hunter/searches", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market, query: query.trim(), location: location.trim() || null, sources: effectiveSources, result_limit: limit, research_mode: "broad", objective: "", website_filter: effectiveWebsite, contact_filter: contactFilter }),
      }))
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
      setSelectedId(job.id)
      const queued = parseHunterJob(await requestHunter(`/api/hunter/searches/${encodeURIComponent(job.id)}/confirm`, { method: "POST" }))
      setJobs((current) => [queued, ...current.filter((item) => item.id !== queued.id)])
      setStage("Consultando as fontes e conferindo os contatos…")
      const completed = await processQueued(job.id)
      setJobs((current) => [completed, ...current.filter((item) => item.id !== completed.id)])
      // The same completion may have created CRM rows; refresh server pages that read them.
      router.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : "A busca falhou. Atualize os resultados para ver a busca salva.") }
    finally { setBusy(false); inFlight.current = false }
  }

  function toggleMap() {
    setShowMap((current) => {
      try { window.localStorage.setItem(MAP_PREFERENCE, current ? "off" : "on") } catch { /* preference is optional */ }
      return !current
    })
  }
  function focusLead(id: string) {
    const row = document.getElementById(`lead-${id}`)
    if (!row) return
    row.scrollIntoView({ behavior: "smooth", block: "center" })
    row.animate([{ backgroundColor: "color-mix(in oklab, var(--primary) 22%, transparent)" }, { backgroundColor: "transparent" }], { duration: 1800, easing: "ease-out" })
  }

  async function clearHistory() {
    if (busy || clearing) return
    setClearing(true); setError("")
    try {
      await requestHunter("/api/hunter/searches", { method: "DELETE" })
      ++requestVersion.current
      setJobs([]); setSelectedId(null); setClearReview(false)
      router.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível limpar as buscas.") }
    finally { setClearing(false) }
  }

  return <div className="mx-auto w-full max-w-5xl space-y-6">
    <header>
      <h1 className="text-3xl font-medium tracking-tight">Buscar leads</h1>
      <p className="mt-1 text-sm text-muted-foreground">Descreva quem você procura. A Kiara confere contato e localização antes de mostrar.</p>
    </header>

    <form className="rounded-xl border bg-card p-4" onSubmit={(event) => { event.preventDefault(); void search() }}>
      <fieldset disabled={busy} className="min-w-0 space-y-3">
        <legend className="sr-only">Busca de leads</legend>
        <div className="flex flex-col gap-2 md:flex-row">
          <label htmlFor="hunter-query" className="sr-only">Quem você procura</label>
          <Input id="hunter-query" required minLength={2} maxLength={300} value={query} onChange={(event) => setQuery(event.target.value)} className="h-11 flex-1 text-base md:text-sm" placeholder="Ex.: Dentistas sem site" />
          <label htmlFor="hunter-location" className="sr-only">Cidade ou região</label>
          <Input id="hunter-location" maxLength={160} value={location} onChange={(event) => setLocation(event.target.value)} className="h-11 text-base md:w-60 md:text-sm" placeholder="Cidade ou região" />
          <Button type="submit" className="h-11 px-6" disabled={!canSearch}>{busy ? <Loader2 className="animate-spin" /> : <Search />}Buscar</Button>
        </div>
        <button type="button" aria-expanded={filtersOpen} aria-controls="hunter-filters" onClick={() => setFiltersOpen((open) => !open)} className="flex w-full items-center gap-2 text-left text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className={cn("size-4 shrink-0 transition-transform", filtersOpen && "rotate-180")} aria-hidden="true" />
          <span className="font-medium text-foreground">Filtros</span>
          <span className="truncate">{filterSummary}</span>
        </button>
        {filtersOpen ? <div id="hunter-filters" className="grid gap-4 border-t pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5"><label htmlFor="hunter-limit" className="text-sm font-medium">Quantidade</label><Input id="hunter-limit" className="h-10" type="number" min={1} max={HUNTER_MAX_RESULTS} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(HUNTER_MAX_RESULTS, Number(event.target.value) || 1)))} /></div>
          <div className="space-y-1.5"><label htmlFor="hunter-website" className="text-sm font-medium">Site</label><select id="hunter-website" className={selectClass} value={effectiveWebsite} disabled={inferredWebsite !== "any"} onChange={(event) => setWebsiteFilter(event.target.value as WebsiteFilter)}>{Object.entries(websiteLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          <div className="space-y-1.5"><label htmlFor="hunter-contact" className="text-sm font-medium">Contato</label><select id="hunter-contact" className={selectClass} value={contactFilter} onChange={(event) => setContactFilter(event.target.value as ContactFilter)}>{Object.entries(contactLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          <fieldset className="space-y-1.5"><legend className="text-sm font-medium">Fontes</legend><div className="flex flex-wrap gap-1.5">{(Object.keys(sourceLabels) as Source[]).map((source) => {
            const active = effectiveSources.includes(source)
            const locked = source === "google_maps" && requiresMaps
            return <button key={source} type="button" aria-pressed={active} disabled={locked} onClick={() => toggle(source)} className={cn("rounded-full border px-3 py-1 text-sm transition", active ? "border-primary/50 bg-primary/15" : "text-muted-foreground hover:text-foreground")}>{sourceLabels[source]}</button>
          })}</div></fieldset>
          {requiresMaps ? <p className="text-xs text-muted-foreground sm:col-span-2 lg:col-span-4">“Sem site” usa a ficha do Google Maps: entram só negócios cuja ficha não informa site.</p> : null}
        </div> : null}
      </fieldset>
    </form>

    {error ? <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}

    {showMap && !mapUnavailable && (busy || mapLeads.length) ? <LeadMap3D scanning={busy} leads={busy ? [] : mapLeads} total={latest?.results.length ?? 0}
      query={latest?.query || query} location={latest?.location ?? location} onSelect={focusLead} onUnavailable={() => setMapUnavailable(true)} /> : null}
    {!mapUnavailable && (busy || mapLeads.length) ? <button type="button" onClick={toggleMap} className="-mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"><MapIcon className="size-3.5" aria-hidden="true" />{showMap ? "Ocultar mapa 3D" : "Mostrar mapa 3D"}</button> : null}

    {busy ? <section className="rounded-xl border bg-card"><HunterActivity stage={stage} query={latest?.query || query} location={latest?.location ?? location} sources={latest?.sources ?? effectiveSources} foundCount={latest?.results.length ?? 0} /></section>
      : <HunterResults jobs={jobs} selected={latest} loading={loading || clearing} onRefresh={() => void load()} onClear={() => setClearReview(true)} onSelect={setSelectedId} onBroaden={broaden} />}

    <Dialog open={clearReview} onOpenChange={setClearReview}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Limpar buscas?</DialogTitle><DialogDescription>As buscas desta tela serão removidas. Os contatos já adicionados continuam salvos.</DialogDescription></DialogHeader>
        <DialogFooter><Button variant="outline" onClick={() => setClearReview(false)} disabled={clearing}>Cancelar</Button><Button variant="destructive" onClick={() => void clearHistory()} disabled={clearing}>{clearing ? <Loader2 className="animate-spin" /> : null}Limpar</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
}
