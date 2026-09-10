"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { BriefcaseBusiness, Check, ChevronRight, Globe2, Loader2, MapPinned, Radar, Search, ShieldCheck, SlidersHorizontal, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { HunterResults } from "./hunter-results"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { inferredWebsiteFilter, parseHunterHistory, parseHunterJob, requestHunter, type ContactFilter, type WebsiteFilter, type HunterSource as Source, type HunterJob as Job } from "@/lib/api/hunter-client"
import { cn } from "@/lib/utils"
import styles from "./hunter.module.css"

const sourceInfo = {
  web: { label: "Web", detail: "Sites e páginas públicas indexadas", icon: Globe2 },
  google_maps: { label: "Google Maps", detail: "Estabelecimentos e contatos locais", icon: MapPinned },
  instagram: { label: "Instagram", detail: "Perfis e posts públicos indexados", icon: Users },
  linkedin: { label: "LinkedIn", detail: "Empresas e perfis públicos indexados", icon: BriefcaseBusiness },
} satisfies Record<Source, { label: string; detail: string; icon: typeof Globe2 }>

const websiteLabels = { any: "Qualquer presença digital", without_website: "Sem site informado no Maps", with_website: "Com site identificado" }
const contactLabels = { any: "Todos os contatos disponíveis", phone: "Somente com telefone público", whatsapp: "Somente com WhatsApp identificado" }

export function HunterClient() {
  const router = useRouter()
  const [market, setMarket] = useState<"b2c" | "b2b">("b2c")
  const [query, setQuery] = useState("")
  const [researchMode, setResearchMode] = useState<"broad" | "focused">("broad")
  const [objective, setObjective] = useState("")
  const [location, setLocation] = useState("")
  const [limit, setLimit] = useState(10)
  const [sources, setSources] = useState<Source[]>(["google_maps", "web"])
  const [websiteFilter, setWebsiteFilter] = useState<WebsiteFilter>("any")
  const [contactFilter, setContactFilter] = useState<ContactFilter>("any")
  const [jobs, setJobs] = useState<Job[]>([])
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState("Preparando sua pesquisa…")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const resultsPanel = useRef<HTMLDivElement>(null)
  const requestVersion = useRef(0)
  const inFlight = useRef(false)
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
  const latest = jobs.find((job) => job.id === selectedId) ?? jobs[0]
  function focusResults() {
    requestAnimationFrame(() => {
      resultsPanel.current?.focus({ preventScroll: true })
      resultsPanel.current?.scrollIntoView({ block: "start", behavior: "instant" })
    })
  }
  const effectiveObjective = researchMode === "focused" ? objective.trim() : ""
  const inferredWebsite = inferredWebsiteFilter(query, effectiveObjective)
  const effectiveWebsite = inferredWebsite !== "any" ? inferredWebsite : websiteFilter
  const requiresMaps = effectiveWebsite === "without_website"
  const effectiveSources = requiresMaps && !sources.includes("google_maps") ? [...sources, "google_maps" as Source] : sources
  function toggle(source: Source) {
    if (source === "google_maps" && requiresMaps) return
    setSources((all) => all.includes(source) ? all.filter((item) => item !== source) : [...all, source])
  }
  function broaden(job: Job) {
    setQuery(job.query); setLocation(job.location || ""); setMarket(job.market); setSources(job.sources)
    setResearchMode("broad"); setObjective(""); setWebsiteFilter("any"); setContactFilter("any")
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
        body: JSON.stringify({ market, query: query.trim(), location: location.trim() || null, sources: effectiveSources, result_limit: limit, research_mode: researchMode, objective: effectiveObjective, website_filter: effectiveWebsite, contact_filter: contactFilter }),
      }))
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
      setSelectedId(job.id)
      setStage("Consultando fontes e verificando os critérios…")
      const completed = parseHunterJob(await requestHunter(`/api/hunter/searches/${encodeURIComponent(job.id)}/confirm`, { method: "POST" }, 210_000))
      setJobs((current) => [completed, ...current.filter((item) => item.id !== completed.id)])
      // The same completion may have created/updated CRM rows. Invalidate any
      // prefetched server pages so Dashboard, Pipeline and Inbox read them.
      router.refresh()
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao pesquisar. Atualize os resultados para consultar a pesquisa salva.") }
    finally { setBusy(false); inFlight.current = false; focusResults() }
  }

  return <div className={styles.workspace}>
    <section className={styles.hero} aria-labelledby="hunter-title">
      <div className={styles.heroCopy}>
        <span className={styles.eyebrow}><Radar aria-hidden="true" /> KIARA HUNTER · INTELIGÊNCIA DE PROSPECÇÃO</span>
        <h2 id="hunter-title">Encontre o próximo cliente<br /><em>antes da concorrência.</em></h2>
        <p>Descreva o público ideal. A Kiara cruza sinais públicos, valida os critérios e entrega oportunidades prontas para ação.</p>
        <div className={styles.heroSignals} aria-label="Recursos da pesquisa">
          <span><Check /> Dados verificados</span><span><Check /> CRM automático</span><span><ShieldCheck /> Sem mensagens automáticas</span>
        </div>
      </div>
      <div className={styles.orbStage}><span className={styles.orbHalo} /><KiaraOrb size="lg" active /><span className={styles.orbStatus}>Hunter online</span></div>
    </section>

    <Card className={cn(styles.searchPanel, "gap-0 self-start py-0 shadow-none")}>
      <CardHeader className={cn(styles.panelHeader, "border-b p-5")}>
        <div className="flex items-center gap-2"><SlidersHorizontal className="size-4 text-primary" aria-hidden="true" /><CardTitle className="text-sm font-semibold">Configurar pesquisa</CardTitle></div>
        <p className="mt-1 text-xs text-muted-foreground">Defina seu público. A Kiara verifica as fontes.</p>
      </CardHeader>
      <CardContent className={cn(styles.panelContent, "p-5")}>
        <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); if (query.trim().length >= 2 && effectiveSources.length && !busy) setReview(true) }}>
          <fieldset disabled={busy} className="space-y-5 disabled:opacity-60">
            <div className="space-y-2">
              <Label htmlFor="hunter-query">Quem você quer encontrar?</Label>
              <Input id="hunter-query" required minLength={2} maxLength={300} className="h-11 bg-background text-base sm:text-sm" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Público, profissão, empresa ou nicho" />
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_80px] gap-3">
              <div className="space-y-2"><Label htmlFor="hunter-location">Cidade ou região</Label><Input id="hunter-location" maxLength={200} className="h-10 text-base sm:text-sm" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Localização (opcional)" /></div>
              <div className="space-y-2"><Label htmlFor="hunter-limit">Limite</Label><Input id="hunter-limit" className="h-10 text-base sm:text-sm" type="number" min={1} max={20} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(20, Number(event.target.value))))} /></div>
            </div>
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted-foreground">Perfil de prospecção</legend>
              <div className="grid grid-cols-2 rounded-lg bg-muted p-1">
                {(["b2c", "b2b"] as const).map((item) => <Button key={item} type="button" variant="ghost" onClick={() => setMarket(item)} aria-pressed={market === item} className={cn("h-9 rounded-md text-xs", market === item && "bg-card shadow-sm hover:bg-card")}>
                  {item === "b2c" ? <Users /> : <BriefcaseBusiness />} {item.toUpperCase()} · {item === "b2c" ? "Pessoas" : "Empresas"}
                </Button>)}
              </div>
            </fieldset>
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
            </fieldset>
            <fieldset className="space-y-3">
              <legend className="mb-2 text-xs font-medium text-muted-foreground">Objetivo da pesquisa</legend>
              <div className="flex gap-2">{(["broad", "focused"] as const).map((mode) => <Button type="button" key={mode} variant={researchMode === mode ? "secondary" : "ghost"} aria-pressed={researchMode === mode} onClick={() => setResearchMode(mode)} className="h-9 flex-1 text-xs">{mode === "broad" ? "Pesquisa ampla" : "Com objetivo"}</Button>)}</div>
              {researchMode === "focused" ? <div className="space-y-2"><Label htmlFor="hunter-objective" className="sr-only">Objetivo ou critério de interesse</Label><Textarea id="hunter-objective" maxLength={500} rows={3} value={objective} onChange={(event) => setObjective(event.target.value)} placeholder="O que torna esse lead interessante para você?" className="resize-y text-base sm:text-sm" /><p className="text-xs leading-5 text-muted-foreground">Critérios livres orientam a consulta. Resultados sem comprovação ficam para revisão, fora do pipeline.</p></div> : <p className="text-xs leading-5 text-muted-foreground">Reúne informações públicas do público escolhido, respeitando os filtros acima.</p>}
            </fieldset>
          </fieldset>
          {error && <p role="alert" className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-xs leading-5 text-destructive">{error}</p>}
          <Button type="submit" className={cn(styles.searchButton, "h-12 w-full gap-2")} disabled={query.trim().length < 2 || !effectiveSources.length || busy}>{busy ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <Search />}Revisar pesquisa<ChevronRight className="ml-auto" /></Button>
          <p className="text-center text-[11px] leading-4 text-muted-foreground">Leads aprovados entram no CRM. Nenhuma mensagem é enviada.</p>
        </form>
      </CardContent>
    </Card>

    <div ref={resultsPanel} tabIndex={-1} aria-label="Acompanhamento e resultados da pesquisa" className={cn(styles.resultsPanel, "min-w-0 scroll-mt-20 outline-none focus-visible:ring-2 focus-visible:ring-ring")}>
      <HunterResults jobs={jobs} selected={latest} busy={busy} loading={loading} stage={stage} error={error} onRefresh={() => void load()} onSelect={setSelectedId} onBroaden={broaden} />
    </div>

    <Dialog open={review} onOpenChange={setReview}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" onCloseAutoFocus={(event) => { if (inFlight.current) { event.preventDefault(); focusResults() } }}>
        <DialogHeader><DialogTitle className="flex items-center gap-2"><ShieldCheck className="size-5 text-primary" />Confirmar pesquisa</DialogTitle><DialogDescription>Revise os critérios antes de consultar as fontes externas.</DialogDescription></DialogHeader>
        <div className="space-y-4 py-2">
          <div><p className="text-lg font-semibold tracking-tight">{query}</p><p className="text-sm text-muted-foreground">{location || "Todas as regiões"} · {market.toUpperCase()} · até {limit} resultados</p></div>
          <dl className="divide-y rounded-lg border px-4 text-sm">
            <div className="py-3"><dt className="text-xs text-muted-foreground">Presença digital</dt><dd className="mt-1 font-medium">{websiteLabels[effectiveWebsite]}</dd></div>
            <div className="py-3"><dt className="text-xs text-muted-foreground">Contato necessário</dt><dd className="mt-1 font-medium">{contactLabels[contactFilter]}</dd></div>
            <div className="py-3"><dt className="text-xs text-muted-foreground">Fontes</dt><dd className="mt-1">{effectiveSources.map((source) => sourceInfo[source].label).join(" · ")}</dd></div>
            {effectiveObjective && <div className="py-3"><dt className="text-xs text-muted-foreground">Objetivo para revisão</dt><dd className="mt-1 break-words">{effectiveObjective}</dd></div>}
          </dl>
          {requiresMaps && <p className="text-xs leading-5 text-muted-foreground">Perfis com site informado ou sem evidência suficiente serão excluídos. “Sem site” significa que o campo não foi encontrado no perfil inspecionado do Maps.</p>}
          <p className="rounded-lg bg-muted p-3 text-xs leading-5 text-muted-foreground">Os resultados aceitos são salvos no pipeline e nos contatos do Inbox. Critérios não verificados exigem revisão. Esta ação não envia mensagens nem cria conversas fictícias.</p>
        </div>
        <DialogFooter><Button variant="outline" className="h-10" onClick={() => setReview(false)}>Voltar e editar</Button><Button className="h-10" disabled={busy} onClick={() => void confirm()}><Search />Confirmar e pesquisar</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
}
