export const pipelineStages = [
  { id: "new", label: "Novos", description: "Descobertos pelo Hunter" },
  { id: "qualified", label: "Qualificados", description: "Perfil revisado" },
  { id: "contacted", label: "Em contato", description: "Abordagem registrada" },
  { id: "opportunity", label: "Oportunidades", description: "Negociação em andamento" },
  { id: "won", label: "Ganhos", description: "Negócio concluído" },
  { id: "lost", label: "Perdidos", description: "Fora da operação ativa" },
] as const

export type PipelineStage = typeof pipelineStages[number]["id"]
export type PipelineEntry = {
  id: string
  qualification?: { score: number; temperature: "cold" | "warm" | "hot" | "unknown"; reasons?: string[]; confidence?: number; recommendation?: string } | null
  stage: PipelineStage
  next_action: string | null
  next_action_at?: string | null
  activities?: import("@/lib/api/sales").OutreachActivity[]
  version: number
  updated_at: string
  consumer: {
    id: string
    display_name: string
    instagram_username: string | null
    phone?: string | null
    email?: string | null
    whatsapp_url?: string | null
    source_url?: string | null
    source?: string | null
    website_status?: string | null
    website_url?: string | null
    website_evidence?: string | null
    website_quality_score?: number | null
    website_quality_signals?: string[]
    criterion_status?: string | null
    enrichment?: string | null
    provider?: string | null
    match_reasons?: string[]
    address?: string | null
    research_query?: string | null
    search_id?: string | null
    notes?: string | null
    prospecting_status?: "review_required" | "public_contact"
    quality_gaps?: string[]
    rating?: number | null
    user_rating_count?: number | null
    company?: CompanyData | null
    fit?: LeadFit | null
  }
}

/** Public registry data (Receita Federal) attached to a lead. */
export type CompanyData = {
  cnpj: string
  cnpj_formatted: string
  legal_name: string | null
  trade_name: string | null
  status: string | null
  active: boolean
  opened_at: string | null
  size: string | null
  legal_nature: string | null
  main_activity: string | null
  secondary_activities?: string[]
  capital: number | null
  city: string | null
  state: string | null
  simples: boolean | null
  mei: boolean | null
  partners?: { name: string | null; role: string | null }[]
  source: string
  cnpj_source?: "manual" | "website"
  fetched_at: string
}

/** Explainable 0-100 profile score computed by the API. */
export type LeadFit = { score: number; grade: "A" | "B" | "C" | "D"; label: string; reasons: { points: number; text: string }[]; has_company_data: boolean }

export class PipelineRequestError extends Error {
  readonly status: number
  readonly code: string

  constructor(message: string, status: number, code = "pipeline_error") {
    super(message)
    this.name = "PipelineRequestError"
    this.status = status
    this.code = code
  }
}

export function safePublicUrl(value: unknown): string | null {
  if (typeof value !== "string") return null
  try {
    const url = new URL(value)
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null
  } catch { return null }
}

export function safeWhatsAppUrl(value: unknown): string | null {
  const safe = safePublicUrl(value)
  if (!safe) return null
  const url = new URL(safe)
  if (url.protocol !== "https:") return null
  const digits = url.hostname === "wa.me" ? url.pathname.slice(1) :
    ["api.whatsapp.com", "web.whatsapp.com"].includes(url.hostname) && url.pathname === "/send" ? url.searchParams.get("phone") : null
  return digits && /^[1-9]\d{7,14}$/.test(digits) ? `https://wa.me/${digits}` : null
}

export function phoneHref(value: string | null | undefined): string | null {
  const digits = value?.replace(/[^\d+]/g, "") ?? ""
  return /^\+?\d{8,15}$/.test(digits) ? `tel:${digits}` : null
}

export function whatsappComposerUrl(
  phone: string | null | undefined,
  confirmedUrl: string | null | undefined,
  message: string,
): { url: string; confirmed: boolean } | null {
  const confirmed = safeWhatsAppUrl(confirmedUrl)
  let base = confirmed
  if (!base) {
    const digits = normalizeWhatsAppPhone(phone)
    if (!digits) return null
    base = `https://wa.me/${digits}`
  }
  const text = message.trim()
  return { url: text ? `${base}?text=${encodeURIComponent(text)}` : base, confirmed: Boolean(confirmed) }
}

export function instagramProfileUrl(username: string | null | undefined): string | null {
  const normalized = username?.trim().replace(/^@/, "") ?? ""
  return /^[A-Za-z0-9._]{1,30}$/.test(normalized) ? `https://www.instagram.com/${normalized}/` : null
}

export function parsePipelineEntry(value: unknown): PipelineEntry {
  if (!value || typeof value !== "object") throw new Error("Resposta inválida do Pipeline.")
  const item = value as PipelineEntry
  if (item.consumer?.prospecting_status != null && !["review_required", "public_contact"].includes(item.consumer.prospecting_status)) throw new Error("Validação de prospecção inválida.")
  if (item.consumer?.quality_gaps != null && (!Array.isArray(item.consumer.quality_gaps) || !item.consumer.quality_gaps.every((gap) => typeof gap === "string"))) throw new Error("Evidências de prospecção inválidas.")
  if (item.qualification != null && (!Number.isFinite(item.qualification.score) || item.qualification.score < 0 || item.qualification.score > 100 || !["cold", "warm", "hot", "unknown"].includes(item.qualification.temperature))) throw new Error("Qualificação inválida no CRM.")
  if (typeof item.id !== "string" || !item.id || !pipelineStages.some((stage) => stage.id === item.stage) ||
    !Number.isInteger(item.version) || item.version < 1 || typeof item.updated_at !== "string" || Number.isNaN(Date.parse(item.updated_at)) ||
    (item.next_action != null && typeof item.next_action !== "string") || !item.consumer || typeof item.consumer.id !== "string" ||
    typeof item.consumer.display_name !== "string" || !item.consumer.display_name ||
    (item.consumer.instagram_username != null && typeof item.consumer.instagram_username !== "string")) {
    throw new Error("A API retornou dados incompletos do Pipeline. Tente atualizar.")
  }
  for (const field of ["phone", "email", "whatsapp_url", "source_url", "source", "website_status", "website_url", "website_evidence", "criterion_status", "enrichment", "provider", "address", "research_query", "search_id", "notes"] as const) {
    if (item.consumer[field] != null && typeof item.consumer[field] !== "string") throw new Error("Contato inválido no Pipeline.")
  }
  for (const field of ["website_quality_signals", "match_reasons"] as const) {
    if (item.consumer[field] != null && (!Array.isArray(item.consumer[field]) || item.consumer[field]?.some((value) => typeof value !== "string"))) throw new Error("Evidências inválidas no Pipeline.")
  }
  if (item.consumer.website_quality_score != null && typeof item.consumer.website_quality_score !== "number") throw new Error("Qualidade digital inválida no Pipeline.")
  return { ...item, consumer: { ...item.consumer,
    source_url: safePublicUrl(item.consumer.source_url), website_url: safePublicUrl(item.consumer.website_url),
    whatsapp_url: safeWhatsAppUrl(item.consumer.whatsapp_url),
    fit: parseLeadFit(item.consumer.fit), company: parseCompany(item.consumer.company),
  } }
}

/** Optional extras never break the CRM: anything malformed is dropped. */
export function parseLeadFit(value: unknown): LeadFit | null {
  const fit = value as LeadFit | null
  if (!fit || typeof fit !== "object" || !Number.isFinite(fit.score) || fit.score < 0 || fit.score > 100 || !["A", "B", "C", "D"].includes(fit.grade) || !Array.isArray(fit.reasons)) return null
  return { ...fit, reasons: fit.reasons.filter((reason) => typeof reason?.text === "string" && Number.isFinite(reason.points)).slice(0, 10) }
}

export function parseCompany(value: unknown): CompanyData | null {
  const company = value as CompanyData | null
  return company && typeof company === "object" && typeof company.cnpj === "string" && /^\d{14}$/.test(company.cnpj) ? company : null
}

export function parsePipeline(value: unknown): PipelineEntry[] {
  if (!value || typeof value !== "object" || !Array.isArray((value as { items?: unknown }).items)) throw new Error("Não foi possível ler o Pipeline. Tente atualizar.")
  return (value as { items: unknown[] }).items.map(parsePipelineEntry)
}

export const sourceLabels: Record<string, string> = { google_maps: "Google Maps", web: "Web pública", instagram: "Instagram", facebook: "Facebook", hunter: "Hunter", whatsapp_web: "WhatsApp Web" }

export function leadDisplayName(consumer: PipelineEntry["consumer"]): string {
  const username = consumer.instagram_username?.trim().replace(/^@/, "")
  if (username && /^[A-Za-z0-9._]{1,30}$/.test(username)) return `@${username}`
  const embeddedHandle = consumer.display_name.match(/@([A-Za-z0-9._]{1,30})/i)?.[1]
  if ((consumer.source === "instagram" || consumer.source === "facebook") && embeddedHandle) return `@${embeddedHandle}`
  const cleaned = consumer.display_name
    .replace(/\s*[•|·-]\s*Instagram(?:\s+photos?\s+and\s+videos?)?\s*$/i, "")
    .replace(/\s*Instagram\s+photos?\s+and\s+videos?\s*$/i, "")
    .replace(/\s*[•|·-]\s*Facebook(?:\s+p[aá]gina|\s+perfil)?\s*$/i, "")
    .replace(/\s*Facebook\s*$/i, "")
    .replace(/\s+[.…]{2,}\s*$/u, "")
    .replace(/\s+/g, " ")
    .trim()
  return cleaned || (consumer.source === "instagram" ? "Perfil do Instagram" : consumer.source === "facebook" ? "Página do Facebook" : "Contato sem nome")
}

export function websiteLabel(status: string | null | undefined): string {
  return status === "present" ? "Site informado" : status === "not_listed" ? "Sem site informado na fonte" : "Site não verificado"
}

export async function requestPipeline(path: string, init: RequestInit = {}): Promise<unknown> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 20_000)
  try {
    const response = await fetch(path, { ...init, cache: "no-store", signal: controller.signal })
    let payload: { error?: { code?: string; message?: string } }
    try { payload = await response.json() } catch {
      if (response.status === 412) throw new PipelineRequestError("Este lead foi atualizado em outra sessão.", 412, "version_conflict")
      throw new PipelineRequestError(`A API retornou uma resposta inválida (HTTP ${response.status}).`, response.status, "invalid_response")
    }
    if (response.status === 401) throw new PipelineRequestError("Sua sessão expirou. Entre novamente para acessar o CRM.", 401, payload.error?.code)
    if (response.status === 412) throw new PipelineRequestError("Este lead foi atualizado em outra sessão.", 412, payload.error?.code || "version_conflict")
    if (!response.ok) throw new PipelineRequestError(typeof payload?.error?.message === "string" ? payload.error.message : "Não foi possível atualizar o Pipeline.", response.status, payload.error?.code)
    return payload
  } catch (error) {
    if (controller.signal.aborted || error instanceof TypeError) throw new Error("A conexão com o CRM foi interrompida. Atualize o Pipeline para conferir os dados antes de repetir.")
    throw error
  } finally { clearTimeout(timer) }
}

/**
 * Normalizes a phone number to WhatsApp digits (country code + area code + number).
 *
 * Brazilian numbers are the default: 10 or 11 digits (DDD + number, with or
 * without the leading 0 trunk prefix) receive the 55 country code. Numbers from
 * other countries must be written with an explicit "+" or "00" prefix, otherwise
 * a Brazilian DDD such as 51 would be misread as a foreign country code.
 */
export function normalizeWhatsAppPhone(raw: string | null | undefined): string | null {
  const value = (raw ?? "").trim()
  if (!value) return null
  const international = /^(\+|00)/.test(value)
  let digits = value.replace(/\D/g, "")
  if (value.startsWith("00")) digits = digits.slice(2)
  if (!international) {
    if (/^0\d{10,11}$/.test(digits)) digits = digits.slice(1)
    if (/^\d{10,11}$/.test(digits)) digits = `55${digits}`
    if (!/^55\d{10,11}$/.test(digits)) return null
  }
  return /^[1-9]\d{7,14}$/.test(digits) ? digits : null
}
