"use client"

import { useState } from "react"
import { BadgeCheck, Check, ExternalLink, Globe2, Loader2, Mail, MapPin, MessageCircle, Phone, Plus, RefreshCw, Star, Trash2, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { hunterEvidenceLabel, hunterMissingEvidence, hunterResultLocation, publicEmail, publicPhone, publicWebsiteUrl, publicWhatsappUrl, type HunterJob, type HunterResult } from "@/lib/api/hunter-client"

const sourceLabels: Record<string, string> = { web: "Web", google_maps: "Google Maps", instagram: "Instagram", facebook: "Facebook" }
const statusLabels: Record<string, string> = { completed: "Concluída", running: "Em andamento", pending_confirmation: "Não iniciada", failed: "Não concluída", cancelled: "Cancelada" }

/** Client-facing explanations; configuration details stay in the collapsed technical section. */
function failureMessage(code: string | null | undefined) {
  if (code === "provider_timeout") return "As fontes demoraram demais para responder. Tente novamente em alguns minutos."
  if (code?.endsWith("_not_configured")) return "Uma das fontes escolhidas ainda não está disponível na sua conta. Desmarque-a nos filtros ou fale com o suporte."
  if (code === "public_index_unavailable" || code === "browser_provider_unavailable") return "As fontes estão indisponíveis agora. Tente novamente em alguns minutos."
  return "A busca não foi concluída. Tente novamente."
}

function resultDisplayName(result: HunterResult) {
  if (result.source === "web" && result.public_data?.display_name?.trim()) return result.public_data.display_name.trim()
  if (result.source === "instagram" || result.source === "facebook") {
    const handle = result.public_data?.profile_handle?.trim().replace(/^@/, "") || result.title.match(/@([A-Za-z0-9._-]{1,50})/)?.[1]
    if (handle && /^[A-Za-z0-9._-]{1,50}$/.test(handle)) return `@${handle}`
    if (result.source === "instagram") {
      try {
        const segment = new URL(result.url).pathname.split("/").filter(Boolean)[0]
        if (segment && /^[A-Za-z0-9._]{1,30}$/.test(segment) && !["p", "reel", "reels"].includes(segment.toLowerCase())) return `@${segment}`
      } catch { /* URL validity is enforced by parseHunterJob. */ }
    }
  }
  return result.title
    .replace(/\s*[•|·-]\s*Instagram(?:\s+photos?\s+and\s+videos?)?\s*$/i, "")
    .replace(/\s*Instagram\s+photos?\s+and\s+videos?\s*$/i, "")
    .replace(/\s*[•|·-]\s*Facebook(?:\s+p[aá]gina|\s+perfil)?\s*$/i, "")
    .replace(/\s*Facebook\s*$/i, "")
    .replace(/\s+[.…]{2,}\s*$/u, "")
    .replace(/\s+/g, " ").trim() || "Resultado sem nome"
}

function LeadRow({ result, searchId, location }: { result: HunterResult; searchId: string; location: string | null }) {
  const [adding, setAdding] = useState(false)
  const [added, setAdded] = useState(Boolean(result.public_data?.lead_id && result.public_data?.pipeline_entry_id))
  const [addError, setAddError] = useState("")
  const data = result.public_data
  const whatsapp = publicWhatsappUrl(data?.whatsapp_url)
  const phone = publicPhone(data?.phone)
  const email = publicEmail(data?.email)
  const website = publicWebsiteUrl(data?.website_url)
  const publication = (result.source === "instagram" || result.source === "facebook") && data?.content_kind === "publication"
  const verified = !data?.manual_import && (
    (result.source === "google_maps" && data?.detail_inspected === true) ||
    (result.source === "instagram" && data?.bio_status === "verified_public_profile") ||
    (result.source === "facebook" && data?.page_status === "verified_public_page")
  )
  const name = resultDisplayName(result)
  const summary = result.summary?.replace(/\s+/g, " ").trim()
  const locationConfirmed = Boolean(data?.address && (data?.detail_inspected || data?.address_evidence === "verified_public_page")) || Boolean(data?.bio_location_evidence)
  const missing = [...new Set([
    ...hunterMissingEvidence(data),
    ...(!phone && !whatsapp ? ["telefone ou WhatsApp público"] : []),
    ...(!locationConfirmed ? ["localização confirmada"] : []),
  ])]
  const blocked = publication || missing.length > 0

  async function addLead() {
    if (adding || added || blocked) return
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

  return <li className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start">
    <div className="min-w-0 flex-1 space-y-1">
      <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 font-medium">
        <span className="min-w-0 break-words">{name}</span>
        <span className="text-xs font-normal text-muted-foreground">{sourceLabels[result.source]}</span>
        <span className={`inline-flex items-center gap-1 text-xs font-normal ${verified ? "text-emerald-400" : "text-muted-foreground"}`}>{verified ? <BadgeCheck className="size-3.5" aria-hidden="true" /> : null}{hunterEvidenceLabel(result.source, data)}</span>
      </h3>
      <p className="flex items-start gap-1.5 text-sm text-muted-foreground"><MapPin className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />{hunterResultLocation(result.source, data, location)}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {phone ? <span className="inline-flex items-center gap-1.5"><Phone className="size-3.5 text-muted-foreground" aria-hidden="true" />{phone}</span> : null}
        {whatsapp ? <a href={whatsapp} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-emerald-400 hover:underline"><MessageCircle className="size-3.5" aria-hidden="true" />WhatsApp</a> : null}
        {email ? <a href={`mailto:${encodeURIComponent(email)}`} className="inline-flex items-center gap-1.5 hover:underline"><Mail className="size-3.5 text-muted-foreground" aria-hidden="true" />{email}</a> : null}
        {website ? <a href={website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 hover:underline"><Globe2 className="size-3.5 text-muted-foreground" aria-hidden="true" />Site</a> : null}
        {result.source === "google_maps" && data?.rating != null ? <span className="inline-flex items-center gap-1.5 text-muted-foreground"><Star className="size-3.5" aria-hidden="true" />{data.rating.toFixed(1)} ({data.user_rating_count ?? 0})</span> : null}
        {!phone && !whatsapp && !email ? <span className="text-muted-foreground">Sem telefone público</span> : null}
      </div>
      {summary ? <p className="line-clamp-2 text-xs text-muted-foreground">{summary}</p> : null}
      {result.source === "web" && data?.name_status === "source_title" ? <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Nome extraído do título da fonte</summary><p className="mt-1 break-words">{data.source_title || result.title}</p><p>O nome comercial não foi confirmado separadamente.</p></details> : null}
      {blocked && !added ? <p className="text-xs text-amber-400">{publication ? "É uma publicação, não um perfil de negócio." : `Falta confirmar: ${missing.join(", ")}.`}</p> : null}
      {addError ? <p role="alert" className="text-xs text-destructive">{addError}</p> : null}
    </div>
    <div className="flex shrink-0 items-center gap-2">
      <Button type="button" size="sm" variant={added ? "ghost" : "outline"} disabled={adding || added || blocked} onClick={() => void addLead()}>{adding ? <Loader2 className="animate-spin" /> : added ? <Check /> : <Plus />}{added ? "Adicionado" : "Adicionar"}</Button>
      <Button asChild size="icon" variant="ghost" className="size-8"><a href={result.url} target="_blank" rel="noopener noreferrer" aria-label={`Abrir a fonte de ${name}`} title="Abrir fonte"><ExternalLink /></a></Button>
    </div>
  </li>
}

export function HunterResults({ jobs, selected, loading, onRefresh, onClear, onSelect, onBroaden }: {
  jobs: HunterJob[]; selected?: HunterJob; loading: boolean
  onRefresh: () => void; onClear: () => void; onSelect: (id: string) => void; onBroaden: (job: HunterJob) => void
}) {
  if (loading && !selected) return <p role="status" className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" />Carregando buscas…</p>
  if (!selected) return <p className="py-12 text-center text-sm text-muted-foreground">Os leads encontrados aparecem aqui.</p>

  const withContact = selected.results.filter((result) => publicPhone(result.public_data?.phone) || publicWhatsappUrl(result.public_data?.whatsapp_url)).length

  return <section aria-labelledby="hunter-results-title" className="overflow-hidden rounded-xl border bg-card">
    <header className="flex flex-col gap-3 border-b px-5 py-4 sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <h2 id="hunter-results-title" className="font-semibold">{selected.status === "completed" ? `${selected.results.length} resultado${selected.results.length === 1 ? "" : "s"}` : statusLabels[selected.status]}</h2>
        <p className="truncate text-sm text-muted-foreground">{selected.query}{selected.location ? ` · ${selected.location}` : ""}{selected.status === "completed" && selected.results.length ? ` · ${withContact} com telefone` : ""}</p>
      </div>
      <div className="flex items-center gap-1">
        {jobs.length > 1 ? <select aria-label="Buscas anteriores" value={selected.id} onChange={(event) => onSelect(event.target.value)} className="h-9 max-w-56 truncate rounded-md border bg-background px-2 text-sm">
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.query}{job.location ? ` · ${job.location}` : ""}</option>)}
        </select> : null}
        <Button variant="ghost" size="icon" className="size-9" disabled={loading} onClick={onRefresh} aria-label="Atualizar resultados">{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}</Button>
        <Button variant="ghost" size="icon" className="size-9" disabled={loading} onClick={onClear} aria-label="Limpar buscas"><Trash2 /></Button>
      </div>
    </header>

    {selected.status === "failed" ? <div role="alert" className="space-y-3 px-5 py-6 text-sm">
      <p className="flex items-start gap-2"><TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-400" aria-hidden="true" />{failureMessage(selected.error_code)}</p>
      <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Detalhes técnicos</summary><p className="mt-2">Código: {selected.error_code || "provider_error"}</p>{selected.warnings?.map((warning, index) => <p key={`${index}-${warning}`} className="mt-1">{warning}</p>)}</details>
    </div> : null}
    {selected.status === "running" ? <p className="px-5 py-6 text-sm text-muted-foreground">A busca ainda está em andamento. Atualize em instantes.</p> : null}
    {selected.status === "cancelled" || selected.status === "pending_confirmation" ? <p className="px-5 py-6 text-sm text-muted-foreground">Esta busca não foi executada. Faça uma nova busca.</p> : null}
    {selected.status === "completed" && !selected.results.length ? <div className="px-5 py-10 text-center">
      <p className="font-medium">Nenhum lead atendeu aos critérios</p>
      <p className="mt-1 text-sm text-muted-foreground">{selected.warnings?.length ? "As fontes não forneceram dados públicos suficientes para confirmar os leads. Confira os avisos abaixo ou ajuste a busca." : "Tente outra região ou ajuste os filtros."}</p>
      <Button variant="outline" className="mt-4" onClick={() => onBroaden(selected)}>Ajustar busca</Button>
    </div> : null}
    {selected.status === "completed" && Boolean(selected.warnings?.length) ? <details className="border-t px-5 py-4 text-sm" open={!selected.results.length}><summary className="cursor-pointer font-medium">Limitações das fontes consultadas</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs leading-5 text-muted-foreground">{selected.warnings?.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul></details> : null}
    {selected.results.length ? <ul className="divide-y">{selected.results.map((result) => <LeadRow key={result.id} result={result} searchId={selected.id} location={selected.location} />)}</ul> : null}
  </section>
}
