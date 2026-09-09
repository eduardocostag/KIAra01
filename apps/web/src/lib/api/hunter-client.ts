export type HunterSource = "web" | "google_maps" | "instagram" | "linkedin"
export type WebsiteFilter = "any" | "without_website" | "with_website"
export type ContactFilter = "any" | "phone" | "whatsapp"
export type HunterPublicData = {
  criterion_status?: "verified" | "not_verified" | "not_requested"
  research_objective?: string
  website_status?: "present" | "not_listed" | "unknown"
  website_url?: string | null
  website_evidence?: string | null
  phone?: string | null
  email?: string | null
  whatsapp_url?: string | null
  website_quality_score?: number | null
  website_quality_signals?: string[]
  match_reasons?: string[]
  address?: string | null
  source_url?: string | null
  lead_id?: string | null
  pipeline_entry_id?: string | null
  crm_status?: string | null
}
export type HunterResult = {
  id: string
  source: HunterSource
  title: string
  url: string
  summary: string | null
  public_data?: HunterPublicData
}
export type HunterJob = {
  id: string
  market: "b2c" | "b2b"
  query: string
  location: string | null
  sources: HunterSource[]
  result_limit: number
  status: "pending_confirmation" | "running" | "completed" | "failed" | "cancelled"
  results: HunterResult[]
  research_mode?: "broad" | "focused"
  objective?: string
  website_filter?: WebsiteFilter
  contact_filter?: ContactFilter
  validation?: { checked: number; accepted: number; excluded: number; unknown: number; source_failures: number }
  warnings?: string[]
  sync_summary?: { created: number; existing: number; skipped: number }
}

const sources = new Set(["web", "google_maps", "instagram", "linkedin"])
const statuses = new Set(["pending_confirmation", "running", "completed", "failed", "cancelled"])

/** A public telephone number is not evidence that WhatsApp is available. */
export function publicWhatsappUrl(value: unknown): string | null {
  if (typeof value !== "string") return null
  try {
    const url = new URL(value)
    if (url.protocol !== "https:" || url.username || url.password || url.port) return null
    if (url.hostname === "wa.me" && /^\/[1-9]\d{7,14}\/?$/.test(url.pathname)) return url.href
    if (["api.whatsapp.com", "web.whatsapp.com"].includes(url.hostname) &&
        url.pathname === "/send" && /^[1-9]\d{7,14}$/.test(url.searchParams.get("phone") ?? "")) return url.href
  } catch { /* Untrusted source links are intentionally not rendered. */ }
  return null
}

export function publicPhone(value: unknown): string | null {
  if (typeof value !== "string" || !/^[\d\s()+.\-]+$/.test(value)) return null
  const digits = value.replace(/\D/g, "")
  return digits.length >= 8 && digits.length <= 15 ? value.trim() : null
}

export function inferredWebsiteFilter(query: string, objective: string): WebsiteFilter {
  const text = `${query} ${objective}`.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
  return /\b(?:sem|nao (?:tem|tenham|possui|possuem))\s+(?:um\s+)?(?:site|website|pagina web)\b/.test(text) ? "without_website" : "any"
}

export function parseHunterJob(value: unknown): HunterJob {
  if (!value || typeof value !== "object") throw new Error("A API retornou uma pesquisa inválida. Tente atualizar os resultados.")
  const job = value as HunterJob
  if (typeof job.id !== "string" || !job.id || typeof job.query !== "string" ||
      !["b2b", "b2c"].includes(job.market) || !statuses.has(job.status) ||
      !Array.isArray(job.sources) || !job.sources.every((source) => sources.has(source)) ||
      !Array.isArray(job.results) || !job.results.every((result) => {
        if (!result || typeof result.id !== "string" || typeof result.title !== "string" ||
            typeof result.url !== "string" || !sources.has(result.source) ||
            (result.summary != null && typeof result.summary !== "string")) return false
        if (result.public_data != null) {
          if (typeof result.public_data !== "object" || Array.isArray(result.public_data)) return false
          const data = result.public_data
          const textFields = [data.research_objective, data.website_url, data.website_evidence, data.phone, data.email, data.whatsapp_url, data.address, data.source_url, data.lead_id, data.pipeline_entry_id, data.crm_status]
          if (!textFields.every((field) => field == null || typeof field === "string")) return false
          if (data.website_status && !["present", "not_listed", "unknown"].includes(data.website_status)) return false
          if (data.criterion_status && !["verified", "not_verified", "not_requested"].includes(data.criterion_status)) return false
          if (data.website_quality_score != null && (typeof data.website_quality_score !== "number" || data.website_quality_score < 0 || data.website_quality_score > 100)) return false
          if (data.match_reasons != null && (!Array.isArray(data.match_reasons) || !data.match_reasons.every(item => typeof item === "string"))) return false
        }
        try { return ["https:", "http:"].includes(new URL(result.url).protocol) } catch { return false }
      })) throw new Error("A API retornou dados incompletos. Tente atualizar os resultados.")
  if (job.warnings != null && (!Array.isArray(job.warnings) || !job.warnings.every((warning) => typeof warning === "string"))) {
    throw new Error("A API retornou avisos inválidos. Tente atualizar os resultados.")
  }
  for (const counts of [job.validation, job.sync_summary]) {
    if (counts != null && (typeof counts !== "object" || Object.values(counts).some((count) => typeof count !== "number" || !Number.isFinite(count) || count < 0))) {
      throw new Error("A API retornou uma contagem inválida. Tente atualizar os resultados.")
    }
  }
  return job
}

export function parseHunterHistory(value: unknown): HunterJob[] {
  if (!value || typeof value !== "object" || !Array.isArray((value as { items?: unknown }).items)) {
    throw new Error("Não foi possível ler o histórico. Tente atualizar os resultados.")
  }
  return (value as { items: unknown[] }).items.map(parseHunterJob)
}

export async function requestHunter(path: string, init: RequestInit = {}, timeoutMs = 20_000): Promise<unknown> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(path, { ...init, cache: "no-store", signal: controller.signal })
    let value: unknown
    try { value = await response.json() } catch {
      throw new Error("O servidor não retornou os dados da pesquisa. Atualize os resultados para verificar se ela terminou.")
    }
    if (!response.ok) {
      if (response.status === 401) throw new Error("Sua sessão expirou. Entre novamente para acessar suas pesquisas.")
      const message = (value as { error?: { message?: unknown } } | null)?.error?.message
      throw new Error(typeof message === "string" ? message : `Não foi possível concluir a consulta (HTTP ${response.status}).`)
    }
    return value
  } catch (error) {
    if (controller.signal.aborted) throw new Error("O servidor demorou a responder. A pesquisa pode continuar em execução; use Atualizar resultados antes de repetir.")
    if (error instanceof TypeError) throw new Error("Falha de conexão. Use Atualizar resultados para consultar a pesquisa salva.")
    throw error
  } finally { clearTimeout(timeout) }
}
