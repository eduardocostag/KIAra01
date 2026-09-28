"use client"

import { useState } from "react"
import { ArrowRight, AtSign, Check, Filter, Globe2, ListFilter, Loader2, MapPin, Phone, Plus, Radar, RefreshCw, Trash2, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { publicPhone, publicWhatsappUrl, type HunterJob, type HunterResult, type HunterSource } from "@/lib/api/hunter-client"
import { HunterActivity } from "./hunter-activity"
import styles from "./hunter.module.css"

const labels: Record<string, string> = { web: "Web pública", google_maps: "Google Maps", instagram: "Instagram", facebook: "Facebook" }
const statuses: Record<string, string> = { completed: "Concluída", running: "Em execução", pending_confirmation: "Aguardando confirmação", failed: "Falhou", cancelled: "Cancelada" }
const failureMessages: Record<string, string> = {
  provider_timeout: "As fontes ultrapassaram o tempo de resposta. Aguarde alguns minutos, use Atualizar resultados e, se persistir, contate o administrador.",
  provider_error: "As fontes selecionadas falharam. Veja abaixo qual fonte falhou e a ação necessária.",
  exa_not_configured: "A busca Web não está configurada. Peça ao administrador para configurar EXA_API_KEY.",
  firecrawl_not_configured: "A busca alternativa não está configurada. Peça ao administrador para configurar FIRECRAWL_API_KEY.",
  public_index_unavailable: "Os provedores de busca pública estão indisponíveis. Tente novamente e, se persistir, peça ao administrador para revisar Exa e Firecrawl.",
  browserbase_not_configured: "O Google Maps não está configurado. Peça ao administrador para configurar Browserbase ou Obscura.",
  browser_provider_unavailable: "O navegador do Google Maps está indisponível. Tente novamente e, se persistir, peça ao administrador para revisar Browserbase ou Obscura.",
}

function resultDisplayName(result: HunterResult) {
  if (result.source === "instagram") {
    const handle = result.public_data?.profile_handle?.trim().replace(/^@/, "") || result.title.match(/@([A-Za-z0-9._]{1,30})/)?.[1]
    if (handle && /^[A-Za-z0-9._]{1,30}$/.test(handle)) return `@${handle}`
    try {
      const segment = new URL(result.url).pathname.split("/").filter(Boolean)[0]
      if (segment && /^[A-Za-z0-9._]{1,30}$/.test(segment) && !["p", "reel", "reels"].includes(segment.toLowerCase())) return `@${segment}`
    } catch { /* URL validity is enforced by parseHunterJob. */ }
  }
  if (result.source === "facebook") {
    const handle = result.public_data?.profile_handle?.trim().replace(/^@/, "") || result.title.match(/@([A-Za-z0-9._-]{1,50})/)?.[1]
    if (handle && /^[A-Za-z0-9._-]{1,50}$/.test(handle)) return `@${handle}`
  }
  return result.title
    .replace(/\s*[•|·-]\s*Instagram(?:\s+photos?\s+and\s+videos?)?\s*$/i, "")
    .replace(/\s*Instagram\s+photos?\s+and\s+videos?\s*$/i, "")
    .replace(/\s*[•|·-]\s*Facebook(?:\s+p[aá]gina|\s+perfil)?\s*$/i, "")
    .replace(/\s*Facebook\s*$/i, "")
    .replace(/\s+[.…]{2,}\s*$/u, "")
    .replace(/\s+/g, " ").trim() || "Resultado sem nome"
}

function LeadRow({ result, searchId, location, historical }: { result: HunterResult; searchId: string; location: string | null; historical: boolean }) {
  const [adding, setAdding] = useState(false)
  const [added, setAdded] = useState(Boolean(result.public_data?.lead_id && result.public_data?.pipeline_entry_id))
  const [addError, setAddError] = useState("")
  const data = result.public_data
  const whatsapp = publicWhatsappUrl(data?.whatsapp_url)
  const phone = publicPhone(data?.phone)
  const whatsappNumber = whatsapp ? new URL(whatsapp).hostname === "wa.me" ? new URL(whatsapp).pathname.replace(/\//g, "") : new URL(whatsapp).searchParams.get("phone") : null
  const contact = phone || (whatsappNumber ? `+${whatsappNumber}` : null)
  const publication = (result.source === "instagram" || result.source === "facebook") && data?.content_kind === "publication"
  const verified = data?.bio_status === "verified_public_profile" || data?.manual_import
  const displayName = resultDisplayName(result)
  const category = result.summary?.split(/[.!?\n]/)[0]?.trim().slice(0, 70) || "Lead encontrado"
  const subtitle = `${category}${location ? ` · ${location}` : ""}`
  const resolvedLocation = result.source === "instagram" || result.source === "facebook"
    ? data?.location_evidence ? location || "Região citada no índice" : "Localização não confirmada"
    : data?.address || location || "Localização não informada"
  async function addLead() {
    if (adding || added) return
    setAdding(true); setAddError("")
    try {
      const response = await fetch(`/api/hunter/searches/${encodeURIComponent(searchId)}/results/${encodeURIComponent(result.id)}/add-lead`, { method: "POST" })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível adicionar este lead.")
      setAdded(true)
    } catch (error) {
      setAddError(error instanceof Error ? error.message : "Não foi possível adicionar este lead.")
    } finally { setAdding(false) }
  }
  return <article className={styles.hunterResultRow} aria-label={displayName}>
    <div className={styles.hunterResultAvatar} aria-hidden="true">{displayName.replace(/^@/, "").slice(0, 1).toUpperCase()}</div>
    <div className={styles.hunterResultBody}>
      <div className={styles.hunterResultTop}>
        <div className={styles.hunterIdentity}><h3>{displayName}</h3><p>{subtitle}</p></div>
        <div className={styles.hunterBadges}>
          <span className={contact ? styles.badgePositive : styles.badgeMuted}>{contact ? <><Phone />Telefone encontrado</> : <>Telefone não encontrado</>}</span>
          <span className={result.source === "instagram" ? styles.badgeInstagram : styles.badgeSource}>{labels[result.source]}</span>
          <span className={verified ? styles.badgeSource : styles.badgeWarning}>{publication ? "Publicação" : verified ? "Perfil confirmado" : historical ? "Não verificado" : "Trecho indexado"}</span>
        </div>
      </div>
      <div className={styles.hunterResultMeta}>
        <span><Phone />{contact || "Telefone não encontrado"}</span>
      </div>
      <div className={styles.hunterResultBottom}>
        <span><MapPin />{resolvedLocation}</span>
        <div className={styles.hunterResultActions}>
          <Button type="button" size="sm" variant="outline" className={styles.hunterAddButton} disabled={adding || added} onClick={() => void addLead()}>{adding ? <Loader2 className="animate-spin" /> : added ? <Check /> : <Plus />}{added ? "Adicionado" : "Adicionar lead"}</Button>
          <Button asChild size="sm" className={styles.hunterDetailsButton}><a href={result.url} target="_blank" rel="noopener noreferrer" aria-label={`Ver detalhes de ${displayName}`}>Ver detalhes<ArrowRight /></a></Button>
        </div>
      </div>
      {addError ? <p role="alert" className={styles.hunterAddError}>{addError}</p> : null}
    </div>
  </article>
}

export function HunterResults({ jobs, selected, busy, loading, stage, error, activeQuery, activeLocation, activeSources, onRefresh, onClear, onSelect, onBroaden }: {
  jobs: HunterJob[]; selected?: HunterJob; busy: boolean; loading: boolean; stage: string; error: string
  activeQuery: string; activeLocation: string; activeSources: HunterSource[]
  onRefresh: () => void; onClear: () => void; onSelect: (id: string) => void; onBroaden: (job: HunterJob) => void
}) {
  const historical = Boolean(selected && !selected.validation)
  const withPhone = selected?.results.filter(result => publicPhone(result.public_data?.phone)).length ?? 0
  const discoveredLocations = selected?.results.flatMap((result) => result.public_data?.address ? [result.public_data.address] : []) ?? []
  return <Card className={styles.resultsCard}>
    <CardHeader className={styles.resultsHeader}>
      <div className={styles.hunterResultsToolbar}>
        <CardTitle className={styles.resultsTitle}>Resultados ({selected?.results.length ?? 0})</CardTitle>
        <div className={styles.hunterSortControls}>
          {jobs.length > 0 && <><span>Ordenar por</span><Select disabled={busy} value={selected?.id ?? jobs[0].id} onValueChange={onSelect}><SelectTrigger id="hunter-history" aria-label="Histórico e ordenação dos resultados" className={styles.hunterSortTrigger}><SelectValue /></SelectTrigger><SelectContent position="popper" className="max-w-[calc(100vw-3rem)]">{jobs.map((job) => <SelectItem key={job.id} value={job.id}><span className="block max-w-[60vw] truncate sm:max-w-lg">{job.query} · {statuses[job.status]} · {job.results.length} resultados</span></SelectItem>)}</SelectContent></Select></>}
          {jobs.length > 0 && <Button variant="ghost" size="icon" className={styles.hunterToolbarButton} disabled={loading || busy} onClick={onClear} aria-label="Limpar resultados"><Trash2 /></Button>}
          <Button variant="ghost" size="icon" className={styles.hunterToolbarButton} disabled={loading || busy} onClick={onRefresh} aria-label="Atualizar resultados">{loading ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}</Button>
        </div>
      </div>
    </CardHeader>
    <CardContent className="p-0">
      {error && <div role="alert" className="m-4 flex gap-3 rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-sm"><TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" /><div><strong className="block">Não foi possível concluir a consulta</strong><p className="mt-1 text-xs leading-5 text-muted-foreground">{error}</p>{selected?.results.length ? <p className="mt-2 text-xs">Os resultados já carregados continuam disponíveis abaixo.</p> : null}</div></div>}
      {busy ? <HunterActivity stage={stage} query={selected?.query || activeQuery} location={selected?.location || activeLocation} sources={selected?.sources || activeSources} foundCount={selected?.results.length ?? 0} discoveries={discoveredLocations} /> : loading && !selected ? <div role="status" className="grid min-h-80 place-items-center text-center text-sm text-muted-foreground"><div><Loader2 className="mx-auto mb-3 size-6 animate-spin motion-reduce:animate-none" />Carregando pesquisas salvas…</div></div> : !selected ? !error && <div className={styles.discoveryIntro}><div className={styles.discoveryScene} aria-hidden="true"><span className={styles.discoveryOrbit} /><span className={styles.discoveryOrbitAlt} /><span className={styles.discoveryOrb}><i /><i /></span><span className={`${styles.sourceBubble} ${styles.instagramBubble}`}><AtSign /></span><span className={`${styles.sourceBubble} ${styles.mapsBubble}`}><MapPin /></span><span className={`${styles.sourceBubble} ${styles.webBubble}`}><Globe2 /></span></div><h2>Defina o público e deixe que eu encontro as oportunidades para você.</h2><div className={styles.discoveryBenefits}><div><span><Globe2 /></span><strong>Múltiplas fontes</strong><small>Instagram, Maps, sites e mais</small></div><div><span><Filter /></span><strong>Filtros inteligentes</strong><small>Encontre exatamente o seu público</small></div><div><span><Radar /></span><strong>Resultados organizados</strong><small>Leads prontos para revisar</small></div></div></div> : <>
        <div className={styles.summaryBlock} role="status" aria-live="polite">
          <div className={styles.summaryIcon}>{selected.status === "completed" ? <Check /> : <Radar />}</div>
          <div className={styles.summaryIdentity}><h2>{selected.status === "completed" ? "Pesquisa concluída" : statuses[selected.status]}</h2><p>{selected.query}{selected.location ? ` · ${selected.location}` : ""}</p></div>
          <div className={styles.summaryMetrics}>
            <span><strong>{selected.results.length}</strong> resultado{selected.results.length === 1 ? "" : "s"}</span>
            {selected.validation && <span><strong>{withPhone}</strong> com telefone</span>}
          </div>
        </div>
        {selected.status === "running" && <p className="p-5 text-sm leading-6 text-muted-foreground">A última atualização indica que a pesquisa está em execução. Use Atualizar resultados para consultar o estado atual.</p>}
        {selected.status === "failed" && <div role="alert" className="p-5 text-sm text-destructive"><p className="font-semibold">A pesquisa falhou</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{failureMessages[selected.error_code ?? ""] ?? "A fonte externa não concluiu a pesquisa. Tente novamente e, se persistir, contate o administrador."} Código: {selected.error_code || "provider_error"}.</p>{selected.warnings?.length ? <ul className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">{selected.warnings.map((warning, index) => <li key={`${index}-${warning}`} className="rounded-md border border-destructive/15 bg-background/40 px-3 py-2">{warning}</li>)}</ul> : null}</div>}
        {selected.status === "cancelled" && <p className="p-5 text-sm">Esta pesquisa foi cancelada.</p>}
        {selected.status === "pending_confirmation" && <p className="p-5 text-sm text-muted-foreground">A pesquisa foi registrada, mas a execução ainda não foi confirmada. Prepare e confirme uma nova busca.</p>}
        {selected.status === "completed" && !selected.results.length && <div className="flex min-h-64 flex-col items-center justify-center px-6 py-10 text-center"><ListFilter className="size-7 text-muted-foreground" /><h3 className="mt-4 font-semibold">Nenhum resultado encontrado</h3><p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Nenhum contato atendeu aos filtros com evidência suficiente nas fontes consultadas. Revise a região ou os critérios; dados não confirmados não são apresentados como correspondências.</p><Button variant="outline" className="mt-5 h-10" onClick={() => onBroaden(selected)}>Ajustar pesquisa</Button></div>}
        <div className={styles.leadsGrid}>{selected.results.map((result) => <LeadRow key={result.id} result={result} searchId={selected.id} location={selected.location} historical={historical} />)}</div>
      </>}
    </CardContent>
  </Card>
}
