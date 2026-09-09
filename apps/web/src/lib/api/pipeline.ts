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
    whatsapp_url?: string | null
    source_url?: string | null
    source?: string | null
    website_status?: string | null
    website_url?: string | null
    address?: string | null
    research_query?: string | null
    search_id?: string | null
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
    let digits = phone?.replace(/\D/g, "") ?? ""
    if ((digits.length === 10 || digits.length === 11) && !digits.startsWith("55")) digits = `55${digits}`
    if (!/^55\d{10,11}$/.test(digits)) return null
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
  if (typeof item.id !== "string" || !item.id || !pipelineStages.some((stage) => stage.id === item.stage) ||
    !Number.isInteger(item.version) || item.version < 1 || typeof item.updated_at !== "string" || Number.isNaN(Date.parse(item.updated_at)) ||
    (item.next_action != null && typeof item.next_action !== "string") || !item.consumer || typeof item.consumer.id !== "string" ||
    typeof item.consumer.display_name !== "string" || !item.consumer.display_name ||
    (item.consumer.instagram_username != null && typeof item.consumer.instagram_username !== "string")) {
    throw new Error("A API retornou dados incompletos do Pipeline. Tente atualizar.")
  }
  for (const field of ["phone", "whatsapp_url", "source_url", "source", "website_status", "website_url", "address", "research_query", "search_id"] as const) {
    if (item.consumer[field] != null && typeof item.consumer[field] !== "string") throw new Error("Contato inválido no Pipeline.")
  }
  return { ...item, consumer: { ...item.consumer,
    source_url: safePublicUrl(item.consumer.source_url), website_url: safePublicUrl(item.consumer.website_url),
    whatsapp_url: safeWhatsAppUrl(item.consumer.whatsapp_url),
  } }
}

export function parsePipeline(value: unknown): PipelineEntry[] {
  if (!value || typeof value !== "object" || !Array.isArray((value as { items?: unknown }).items)) throw new Error("Não foi possível ler o Pipeline. Tente atualizar.")
  return (value as { items: unknown[] }).items.map(parsePipelineEntry)
}

export const sourceLabels: Record<string, string> = { google_maps: "Google Maps", web: "Web pública", instagram: "Instagram", linkedin: "LinkedIn", hunter: "Hunter" }

export function websiteLabel(status: string | null | undefined): string {
  return status === "present" ? "Site informado" : status === "not_listed" ? "Sem site informado na fonte" : "Site não verificado"
}

export async function requestPipeline(path: string, init: RequestInit = {}): Promise<unknown> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 20_000)
  try {
    const response = await fetch(path, { ...init, cache: "no-store", signal: controller.signal })
    let payload: { error?: { message?: string } }
    try { payload = await response.json() } catch { throw new Error("A API retornou uma resposta inválida. Atualize o Pipeline antes de repetir.") }
    if (response.status === 401) throw new Error("Sua sessão expirou. Entre novamente para acessar o CRM.")
    if (response.status === 412) throw new Error("Este lead foi alterado em outra sessão. Atualize o Pipeline antes de tentar novamente.")
    if (!response.ok) throw new Error(typeof payload?.error?.message === "string" ? payload.error.message : "Não foi possível atualizar o Pipeline.")
    return payload
  } catch (error) {
    if (controller.signal.aborted || error instanceof TypeError) throw new Error("A conexão com o CRM foi interrompida. Atualize o Pipeline para conferir os dados antes de repetir.")
    throw error
  } finally { clearTimeout(timer) }
}
