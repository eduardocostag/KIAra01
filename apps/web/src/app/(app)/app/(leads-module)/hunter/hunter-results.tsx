"use client"

import { useRef, useState, type CSSProperties } from "react"
import { BadgeCheck, Check, ExternalLink, Flame, Globe2, Loader2, Mail, MapPin, MessageCircle, Phone, Plus, RefreshCw, Snowflake, Star, Sun, Trash2, TriangleAlert, UserRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { burst } from "@/components/fx/fx"
import { displayPhone, hunterEvidenceLabel, hunterMissingEvidence, hunterResultLocation, publicEmail, publicPhone, publicWebsiteUrl, publicWhatsappUrl, type HunterJob, type HunterResult } from "@/lib/api/hunter-client"

const sourceLabels: Record<string, string> = { web: "Web", google_maps: "Google Maps", instagram: "Instagram", facebook: "Facebook" }
const tierStyles = {
  confirmed: { label: "Confirmado", className: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300" },
  probable: { label: "Provável", className: "border-sky-400/40 bg-sky-400/10 text-sky-300" },
  to_review: { label: "A conferir", className: "border-amber-400/40 bg-amber-400/10 text-amber-300" },
} as const
const temperatureStyles = {
  hot: { label: "Quente", icon: Flame, className: "bg-rose-500/15 text-rose-300" },
  warm: { label: "Morno", icon: Sun, className: "bg-amber-400/15 text-amber-300" },
  cold: { label: "Frio", icon: Snowflake, className: "bg-sky-400/15 text-sky-300" },
} as const

/** Confidence tier computed by the API. */
function TierBadge({ data }: { data: HunterResult["public_data"] }) {
  const tier = data?.lead_tier ? tierStyles[data.lead_tier] : null
  return tier ? <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${tier.className}`}>{tier.label}</span> : null
}

const ringColors = { hot: "#fb7185", warm: "#fbbf24", cold: "#38bdf8" } as const

/** The 0–100 lead score as a ring colored by temperature; the reasons are listed beside it. */
function ScoreRing({ data }: { data: HunterResult["public_data"] }) {
  const score = typeof data?.lead_score === "number" ? Math.round(Math.max(0, Math.min(100, data.lead_score))) : null
  const temperature = data?.temperature ? temperatureStyles[data.temperature] : null
  if (score === null) return null
  const color = ringColors[data?.temperature ?? "cold"]
  const Icon = temperature?.icon
  const circumference = 2 * Math.PI * 21
  return <div className="flex shrink-0 flex-col items-center gap-1" role="img" aria-label={`Nota ${score} de 100${temperature ? `, lead ${temperature.label.toLowerCase()}` : ""}`}>
    <span className="relative grid size-12 place-items-center sm:size-14">
      <svg viewBox="0 0 48 48" className="absolute inset-0 -rotate-90" aria-hidden="true">
        <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeWidth="4" className="text-muted/60" />
        <circle cx="24" cy="24" r="21" fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - score / 100)} className="transition-[stroke-dashoffset] duration-700" />
      </svg>
      <span className="text-base font-semibold tabular-nums">{score}</span>
    </span>
    {temperature && Icon ? <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${temperature.className}`}><Icon className="size-2.5" aria-hidden="true" />{temperature.label}</span> : null}
  </div>
}

/** Short tags for what makes the lead worth calling (or what still needs checking). */
function reasonTags(data: HunterResult["public_data"], hasWhatsapp: boolean, website: string | null) {
  const tags: { text: string; tone: "good" | "warn" | "plain" }[] = []
  if (data?.website_status === "not_listed" && !website) tags.push({ text: "Sem site", tone: "good" })
  if (hasWhatsapp) tags.push({ text: "WhatsApp", tone: "good" })
  else if (data?.whatsapp_probable) tags.push({ text: "WhatsApp provável", tone: "plain" })
  for (const signal of data?.website_quality_signals ?? []) tags.push({ text: signal, tone: "good" })
  for (const reason of data?.temperature_reasons ?? []) {
    // The short tags above and the rating line already say these; the reason would only repeat them.
    if (/whatsapp/i.test(reason) && (hasWhatsapp || data?.whatsapp_probable)) continue
    if (/sem site/i.test(reason) && tags.some((tag) => tag.text === "Sem site")) continue
    if (/avalia|nota \d/i.test(reason) && data?.rating != null) continue
    tags.push({ text: reason, tone: /ainda não|confira/i.test(reason) ? "warn" : "plain" })
  }
  const seen = new Set<string>()
  return tags.filter((tag) => { const key = tag.text.toLowerCase(); if (seen.has(key)) return false; seen.add(key); return true }).slice(0, 6)
}
const toneClass = { good: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300", warn: "border-amber-400/30 bg-amber-400/10 text-amber-300", plain: "border-border bg-muted/40 text-muted-foreground" } as const

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

function LeadRow({ result, searchId, location, index }: { result: HunterResult; searchId: string; location: string | null; index: number }) {
  const addRef = useRef<HTMLSpanElement>(null)
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
  // Not fully confirmed leads can still be added; they enter the CRM marked as Provável / A conferir.
  const blocked = publication

  async function addLead() {
    if (adding || added || blocked) return
    setAdding(true); setAddError("")
    try {
      const response = await fetch(`/api/hunter/searches/${encodeURIComponent(searchId)}/results/${encodeURIComponent(result.id)}/add-lead`, { method: "POST" })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível adicionar este lead.")
      setAdded(true)
      burst(addRef.current, "#34d399")
    } catch (error) {
      setAddError(error instanceof Error ? error.message : "Não foi possível adicionar este lead.")
    } finally { setAdding(false) }
  }

  const temperatureClass = data?.temperature === "hot" ? "fx-hot" : data?.temperature === "warm" ? "fx-hot fx-warm" : data?.temperature === "cold" ? "fx-hot fx-cold" : ""
  const tags = reasonTags(data, Boolean(whatsapp), website)
  return <li id={`lead-${result.id}`} style={{ "--i": index } as CSSProperties} className={`fx-rise fx-spot flex scroll-mt-24 flex-col gap-3 px-4 py-4 transition-colors sm:gap-4 sm:px-5 hover:bg-muted/20 sm:flex-row sm:items-start ${temperatureClass}`}>
    <div className="flex min-w-0 flex-1 gap-3 sm:gap-4">
      <ScoreRing data={data} />
      <div className="min-w-0 flex-1 space-y-1.5">
        <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 font-medium">
          <span className="min-w-0 break-words text-[15px]">{name}</span>
          <TierBadge data={data} />
        </h3>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          <span>{sourceLabels[result.source]}</span>
          <span className={`inline-flex items-center gap-1 ${verified ? "text-emerald-400" : ""}`}>{verified ? <BadgeCheck className="size-3.5" aria-hidden="true" /> : null}{hunterEvidenceLabel(result.source, data)}</span>
          {result.source === "google_maps" && data?.rating != null ? <span className="inline-flex items-center gap-1"><Star className="size-3 fill-amber-400 text-amber-400" aria-hidden="true" />{data.rating.toFixed(1).replace(".", ",")} ({data.user_rating_count ?? 0})</span> : null}
        </p>
        {data?.decision_maker?.name ? <p className="flex items-start gap-1.5 text-sm"><UserRound className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" /><span><span className="font-medium">{data.decision_maker.name}</span>{data.decision_maker.role ? <span className="text-muted-foreground"> · {data.decision_maker.role}</span> : null}<span className="text-xs text-muted-foreground">{data.decision_maker.source === "receita" ? " · Receita Federal" : data.decision_maker.source === "site" ? " · site da empresa" : " · Google Maps"}</span></span></p> : null}
        <p className="flex items-start gap-1.5 text-sm text-muted-foreground"><MapPin className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />{hunterResultLocation(result.source, data, location)}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {phone ? <a href={`tel:${phone.replace(/[^\d+]/g, "")}`} className="inline-flex min-h-8 items-center gap-1.5 hover:underline"><Phone className="size-3.5 text-muted-foreground" aria-hidden="true" />{displayPhone(phone)}{data?.phone_kind ? <span className="text-xs text-muted-foreground">· {data.phone_kind}</span> : null}</a> : null}
          {email ? <a href={`mailto:${encodeURIComponent(email)}`} className="inline-flex min-h-8 items-center gap-1.5 hover:underline"><Mail className="size-3.5 text-muted-foreground" aria-hidden="true" />{email}</a> : null}
          {website ? <a href={website} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-8 items-center gap-1.5 hover:underline"><Globe2 className="size-3.5 text-muted-foreground" aria-hidden="true" />Site</a> : null}
          {!phone && !whatsapp && !email ? <span className="text-muted-foreground">Sem telefone público</span> : null}
        </div>
        {tags.length ? <ul className="flex flex-wrap gap-1.5" aria-label="Por que este lead">{tags.map((tag) => <li key={tag.text} className={`rounded-full border px-2 py-0.5 text-[11px] ${toneClass[tag.tone]}`}>{tag.text}</li>)}</ul> : null}
        {summary ? <p className="line-clamp-2 text-xs text-muted-foreground">{summary}</p> : null}
        {result.source === "web" && data?.name_status === "source_title" ? <details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Nome extraído do título da fonte</summary><p className="mt-1 break-words">{data.source_title || result.title}</p><p>O nome comercial não foi confirmado separadamente.</p></details> : null}
        {publication && !added ? <p className="text-xs text-amber-400">É uma publicação, não um perfil de negócio.</p>
          : missing.length && !added ? <p className="text-xs text-amber-400">Falta confirmar: {missing.join(", ")}. Confira a fonte antes de abordar.</p> : null}
        {data?.also_found_on?.length ? <p className="text-xs text-muted-foreground">Também encontrado em {data.also_found_on.length} outra(s) fonte(s); os contatos foram reunidos.</p> : null}
        {addError ? <p role="alert" className="text-xs text-destructive">{addError}</p> : null}
      </div>
    </div>
    <div className="grid shrink-0 grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 sm:flex sm:flex-col sm:items-stretch">
      <span ref={addRef} className="relative flex min-w-0"><Button type="button" size="sm" className="h-9 w-full sm:h-8" variant={added ? "ghost" : "default"} disabled={adding || added || blocked} onClick={() => void addLead()}>{adding ? <Loader2 className="animate-spin" /> : added ? <Check /> : <Plus />}{added ? "No funil" : <>Adicionar<span className="hidden sm:inline"> ao funil</span></>}</Button></span>
      {whatsapp ? <Button asChild size="sm" variant="outline" className="h-9 border-emerald-400/40 sm:h-8 text-emerald-300 hover:bg-emerald-400/10 hover:text-emerald-200"><a href={whatsapp} target="_blank" rel="noopener noreferrer"><MessageCircle aria-hidden="true" />WhatsApp</a></Button> : null}
      <Button asChild size="sm" variant="ghost" className="h-9 px-2 text-muted-foreground sm:h-8 sm:px-3"><a href={result.url} target="_blank" rel="noopener noreferrer" aria-label={`Abrir a fonte de ${name}`}><ExternalLink aria-hidden="true" />Fonte</a></Button>
    </div>
  </li>
}

export function HunterResults({ jobs, selected, loading, onRefresh, onClear, onSelect, onBroaden }: {
  jobs: HunterJob[]; selected?: HunterJob; loading: boolean
  onRefresh: () => void; onClear: () => void; onSelect: (id: string) => void; onBroaden: (job: HunterJob) => void
}) {
  if (loading && !selected) return <div role="status" aria-label="Carregando buscas" className="space-y-3 rounded-xl border bg-card p-5">{[0, 1, 2, 3].map((row) => <div key={row} className="space-y-2"><div className="fx-skeleton h-4 w-1/3" /><div className="fx-skeleton h-3 w-2/3" /></div>)}</div>
  if (!selected) return <p className="py-12 text-center text-sm text-muted-foreground">Os leads encontrados aparecem aqui.</p>

  const withContact = selected.results.filter((result) => publicPhone(result.public_data?.phone) || publicWhatsappUrl(result.public_data?.whatsapp_url)).length
  const tierCount = (tier: string) => selected.results.filter((result) => result.public_data?.lead_tier === tier).length
  const hot = selected.results.filter((result) => result.public_data?.temperature === "hot").length
  const breakdown = [tierCount("confirmed") ? `${tierCount("confirmed")} confirmados` : "", tierCount("probable") ? `${tierCount("probable")} prováveis` : "",
    tierCount("to_review") ? `${tierCount("to_review")} a conferir` : "", hot ? `${hot} quentes` : ""].filter(Boolean).join(" · ")

  return <section aria-labelledby="hunter-results-title" className="overflow-hidden rounded-xl border bg-card">
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b px-4 py-3.5 sm:px-5 sm:py-4">
      <div className="min-w-0 flex-1 basis-48">
        <h2 id="hunter-results-title" className="font-semibold">{selected.status === "completed" ? `${selected.results.length} resultado${selected.results.length === 1 ? "" : "s"}` : statusLabels[selected.status]}</h2>
        <p className="truncate text-sm text-muted-foreground">{selected.query}{selected.location ? ` · ${selected.location}` : ""}{selected.status === "completed" && selected.results.length ? ` · ${breakdown || `${withContact} com telefone`}` : ""}</p>
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
    {selected.results.length ? <ul className="divide-y">{selected.results.map((result, index) => <LeadRow key={result.id} index={index} result={result} searchId={selected.id} location={selected.location} />)}</ul> : null}
  </section>
}
