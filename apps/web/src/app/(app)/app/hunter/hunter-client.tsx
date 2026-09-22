"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Check, ChevronRight, Globe2, Loader2, MapPinned, MessagesSquare, Search, ShieldCheck, SlidersHorizontal, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { HunterResults } from "./hunter-results"
import { inferredWebsiteFilter, parseHunterHistory, parseHunterJob, requestHunter, type ContactFilter, type WebsiteFilter, type HunterSource as Source, type HunterJob as Job } from "@/lib/api/hunter-client"
import { cn } from "@/lib/utils"
import styles from "./hunter.module.css"

const sourceInfo = {
  web: { label: "Web", detail: "Sites e páginas públicas indexadas", icon: Globe2 },
  google_maps: { label: "Google Maps", detail: "Estabelecimentos e contatos locais", icon: MapPinned },
  instagram: { label: "Instagram", detail: "Perfis e posts públicos indexados", icon: Users },
  facebook: { label: "Facebook", detail: "Páginas e perfis públicos indexados", icon: MessagesSquare },
} satisfies Record<Source, { label: string; detail: string; icon: typeof Globe2 }>

const websiteLabels = { any: "Qualquer presença digital", without_website: "Sem site informado no Maps", with_website: "Com site identificado" }
const contactLabels = { any: "Todos os contatos disponíveis", phone: "Somente com telefone público", whatsapp: "Somente com WhatsApp identificado" }

const HUNTER_MAX_RESULTS = 100

export function HunterClient() {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [location, setLocation] = useState("")
  const [limit, setLimit] = useState(10)
  const [sources, setSources] = useState<Source[]>(["google_maps", "web"])
  const [websiteFilter, setWebsiteFilter] = useState<WebsiteFilter>("any")
  const [contactFilter, setContactFilter] = useState<ContactFilter>("any")
  const [jobs, setJobs] = useState<Job[]>([])
  const [review, setReview] = useState(false)
  const [clearReview, setClearReview] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState("Preparando sua pesquisa…")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const resultsPanel = useRef<HTMLDivElement>(null)
  const requestVersion = useRef(0)
  const inFlight = useRef(false)
  const processQueued = useCallback(async (id: string) => {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const current = parseHunterJob(await requestHunter(
        `/api/hunter/searches/${encodeURIComponent(id)}/process`, { method: "POST" }, 210_000,
      ))
      setJobs((items) => [current, ...items.filter((item) => item.id !== current.id)])
      if (current.status !== "running") return current
      setStage("Pesquisa preservada na fila; aguardando a próxima tentativa…")
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
      if (version === requestVersion.current) setError(e instanceof Error ? e.message : "Falha ao carregar as pesquisas.")
    } finally { if (version === requestVersion.current) setLoading(false) }
  }, [])
  // Synchronize persisted history without allowing an old GET to replace a new search.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const running = jobs.find((job) => job.status === "running")
    if (!running || inFlight.current || loading) return
    inFlight.current = true
    setBusy(true); setStage("Retomando a pesquisa salva…")
    void processQueued(running.id)
      .then(() => router.refresh())
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Não foi possível retomar a pesquisa."))
      .finally(() => { inFlight.current = false; setBusy(false) })
  }, [jobs, loading, processQueued, router])
  const latest = jobs.find((job) => job.id === selectedId) ?? jobs[0]
  function focusResults() {
    requestAnimationFrame(() => {
      resultsPanel.current?.focus({ preventScroll: true })
      resultsPanel.current?.scrollIntoView({ block: "start", behavior: "instant" })
    })
  }
  const market = /\b(?:empresas?|negócios?|clínicas?|lojas?|agências?|restaurantes?)\b/i.test(query) ? "b2b" : "b2c"
  const inferredWebsite = inferredWebsiteFilter(query, "")
  const effectiveWebsite = inferredWebsite !== "any" ? inferredWebsite : websiteFilter
  const requiresMaps = effectiveWebsite === "without_website"
  const mentionsInstagram = /\b(?:instagram|insta|reels?)\b/i.test(query)
  const mentionsFacebook = /\b(?:facebook|fb|p[aá]gina)\b/i.test(query)
  const sourceSet = new Set<Source>(sources)
  if (requiresMaps) sourceSet.add("google_maps")
  if (mentionsInstagram) sourceSet.add("instagram")
  if (mentionsFacebook) sourceSet.add("facebook")
  const effectiveSources = [...sourceSet]
  function toggle(source: Source) {
    if (source === "google_maps" && requiresMaps) return
    setSources((all) => all.includes(source) ? all.filter((item) => item !== source) : [...all, source])
  }
  function broaden(job: Job) {
    setQuery(job.query); setLocation(job.location || ""); setSources(job.sources)
    setWebsiteFilter("any"); setContactFilter("any")
    document.getElementById("hunter-query")?.focus()
  }
  async function confirm() {
    if (inFlight.current) return
    inFlight.current = true
    ++requestVersion.current
    setLoading(false); setReview(false); setStage("Registrando sua pesquisa…"); setBusy(true); setError("")
    focusResults()
    try {
      const job = parseHunterJob(await requestHunter("/api/hunter/searches", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market, query: query.trim(), location: location.trim() || null, sources: effectiveSources, result_limit: limit, research_mode: "broad", objective: "", website_filter: effectiveWebsite, contact_filter: contactFilter }),
      }))
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
      setSelectedId(job.id)
      setStage("Colocando a pesquisa na fila durável…")
      const queued = parseHunterJob(await requestHunter(`/api/hunter/searches/${encodeURIComponent(job.id)}/confirm`, { method: "POST" }))
      setJobs((current) => [queued, ...current.filter((item) => item.id !== queued.id)])
      setStage("Consultando fontes e verificando os critérios…")
      const completed = await processQueued(job.id)
      setJobs((current) => [completed, ...current.filter((item) => item.id !== completed.id)])
      // The same completion may have created/updated CRM rows. Invalidate any
      // prefetched server pages so Dashboard, Pipeline and Inbox read them.
      router.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao pesquisar. Atualize os resultados para consultar a pesquisa salva.") }
    finally { setBusy(false); inFlight.current = false; focusResults() }
  }

  async function clearHistory() {
    if (busy || clearing) return
    setClearing(true); setError("")
    try {
      await requestHunter("/api/hunter/searches", { method: "DELETE" })
      ++requestVersion.current
      setJobs([]); setSelectedId(null); setClearReview(false)
      router.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : "Não foi possível limpar as pesquisas.") }
    finally { setClearing(false) }
  }

  return <div className={styles.workspace}>
    <header className="mb-6"><h1 id="hunter-title" className="kiara-editorial text-3xl sm:text-4xl">Encontrar contatos</h1><p className="mt-1 text-sm text-muted-foreground">Descreva o cliente ideal em linguagem natural e veja os resultados ao lado.</p></header>

    <Card className={cn(styles.searchPanel, "gap-0 self-start py-0 shadow-none")}>
      <CardHeader className={cn(styles.panelHeader, "border-b p-5")}>
        <div className="flex items-center gap-2"><SlidersHorizontal className="size-4 text-primary" aria-hidden="true" /><CardTitle className="text-sm font-semibold">Configurar pesquisa</CardTitle></div>
        <p className="mt-1 text-xs text-muted-foreground">A Kiara entende segmento, serviço, localização e presença digital.</p>
      </CardHeader>
      <CardContent className={cn(styles.panelContent, "p-5")}>
        <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); if (query.trim().length >= 2 && effectiveSources.length && !busy) setReview(true) }}>
          <fieldset disabled={busy} className="space-y-5 disabled:opacity-60">
            <div className="space-y-2">
              <Label htmlFor="hunter-query">Descreva o cliente que você quer encontrar</Label>
              <Input id="hunter-query" required minLength={2} maxLength={300} className="h-11 bg-background text-base sm:text-sm" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ex.: Dentistas em Porto Alegre" />
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_80px] gap-3">
              <div className="space-y-2"><Label htmlFor="hunter-location">Cidade ou região</Label><Input id="hunter-location" maxLength={160} className="h-10 text-base sm:text-sm" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Localização" /></div>
              <div className="space-y-2"><Label htmlFor="hunter-limit">Limite</Label><Input id="hunter-limit" className="h-10 text-base sm:text-sm" type="number" min={1} max={HUNTER_MAX_RESULTS} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(HUNTER_MAX_RESULTS, Number(event.target.value) || 1)))} /></div>
            </div>
            <div className="space-y-4 border-y py-4">
              <div className="space-y-2">
                <Label htmlFor="hunter-website">Presença digital</Label>
                <Select value={effectiveWebsite} onValueChange={(value) => setWebsiteFilter(value as WebsiteFilter)} disabled={busy || inferredWebsite !== "any"}>
                  <SelectTrigger id="hunter-website" className="h-10 w-full"><SelectValue /></SelectTrigger>
                  <SelectContent position="popper">{Object.entries(websiteLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
                {requiresMaps && <p className="text-xs leading-5 text-muted-foreground">{inferredWebsite !== "any" ? "“Sem site” foi identificado no seu texto. " : ""}Só aceita perfis inspecionados no Maps sem site informado. Isso não comprova ausência de site em toda a internet.</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="hunter-contact">Contato necessário</Label>
                <Select value={contactFilter} onValueChange={(value) => setContactFilter(value as ContactFilter)} disabled={busy}>
                  <SelectTrigger id="hunter-contact" className="h-10 w-full"><SelectValue /></SelectTrigger>
                  <SelectContent position="popper">{Object.entries(contactLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent>
                </Select>
                {contactFilter === "whatsapp" && <p className="text-xs leading-5 text-muted-foreground">Exige um link público de WhatsApp. Um telefone sozinho não é confirmação.</p>}
              </div>
            </div>
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted-foreground">Fontes da pesquisa</legend>
              <div className="grid grid-cols-2 gap-2">{(Object.keys(sourceInfo) as Source[]).map((source) => {
                const info = sourceInfo[source]; const Icon = info.icon; const active = effectiveSources.includes(source)
                return <Button key={source} type="button" variant="outline" title={info.detail} aria-pressed={active} aria-disabled={source === "google_maps" && requiresMaps} onClick={() => toggle(source)} className={cn("h-10 justify-start gap-2 rounded-lg px-3 text-xs", active && "border-primary/35 bg-brand-subtle text-brand-subtle-foreground hover:bg-brand-subtle")}><Icon className="size-3.5" /><span className="flex-1 text-left">{info.label}</span>{active && <Check className="size-3.5" />}</Button>
              })}</div>
              {requiresMaps && <p className="mt-2 text-xs text-muted-foreground">Google Maps incluído para verificar o critério de site.</p>}
              {mentionsInstagram && !sources.includes("instagram") && <p className="mt-2 text-xs text-muted-foreground">Instagram incluído porque foi citado na descrição.</p>}
            </fieldset>
          </fieldset>
          {error && <p role="alert" className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-xs leading-5 text-destructive">{error}</p>}
          <Button type="submit" className={cn(styles.searchButton, "h-12 w-full gap-2")} disabled={query.trim().length < 2 || !effectiveSources.length || busy}>{busy ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <Search />}Revisar pesquisa<ChevronRight className="ml-auto" /></Button>
        </form>
      </CardContent>
    </Card>

    <div ref={resultsPanel} tabIndex={-1} aria-label="Acompanhamento e resultados da pesquisa" className={cn(styles.resultsPanel, "min-w-0 scroll-mt-20 outline-none focus-visible:ring-2 focus-visible:ring-ring")}>
      <HunterResults jobs={jobs} selected={latest} busy={busy || clearing} loading={loading} stage={stage} error={error} onRefresh={() => void load()} onClear={() => setClearReview(true)} onSelect={setSelectedId} onBroaden={broaden} />
    </div>

    <Dialog open={review} onOpenChange={setReview}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" onCloseAutoFocus={(event) => { if (inFlight.current) { event.preventDefault(); focusResults() } }}>
        <DialogHeader><DialogTitle className="flex items-center gap-2"><ShieldCheck className="size-5 text-primary" />Confirmar pesquisa</DialogTitle></DialogHeader>
        <div className="space-y-4 py-2">
          <div><p className="text-lg font-semibold tracking-tight">{query}</p><p className="text-sm text-muted-foreground">{location || "Todas as regiões"} · até {limit} resultados</p></div>
          <dl className="divide-y rounded-lg border px-4 text-sm">
            <div className="py-3"><dt className="text-xs text-muted-foreground">Presença digital</dt><dd className="mt-1 font-medium">{websiteLabels[effectiveWebsite]}</dd></div>
            <div className="py-3"><dt className="text-xs text-muted-foreground">Contato necessário</dt><dd className="mt-1 font-medium">{contactLabels[contactFilter]}</dd></div>
            <div className="py-3"><dt className="text-xs text-muted-foreground">Fontes</dt><dd className="mt-1">{effectiveSources.map((source) => sourceInfo[source].label).join(" · ")}</dd></div>
          </dl>
          {requiresMaps && <p className="text-xs leading-5 text-muted-foreground">Perfis com site informado ou sem evidência suficiente serão excluídos. “Sem site” significa que o campo não foi encontrado no perfil inspecionado do Maps.</p>}
        </div>
        <DialogFooter><Button variant="outline" className="h-10" onClick={() => setReview(false)}>Voltar e editar</Button><Button className="h-10" disabled={busy} onClick={() => void confirm()}><Search />Confirmar e pesquisar</Button></DialogFooter>
      </DialogContent>
    </Dialog>
    <Dialog open={clearReview} onOpenChange={setClearReview}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Limpar resultados do Hunter?</DialogTitle><DialogDescription>As pesquisas desta tela serão removidas. Os contatos do Inbox continuarão salvos.</DialogDescription></DialogHeader>
        <DialogFooter><Button variant="outline" onClick={() => setClearReview(false)} disabled={clearing}>Cancelar</Button><Button variant="destructive" onClick={() => void clearHistory()} disabled={clearing}>{clearing ? <Loader2 className="animate-spin" /> : null}Limpar resultados</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
}
