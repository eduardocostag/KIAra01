/** Browser calls to the growth features through /api/growth (knowledge, team, plan, drafts, presets). */
export async function growth<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/growth/${path}`, { ...init, cache: "no-store", headers: { "Content-Type": "application/json", ...init.headers } })
  if (response.status === 204) return undefined as T
  const payload = await response.json().catch(() => null) as (T & { error?: { message?: string } }) | null
  if (!response.ok) throw new Error(payload?.error?.message || (response.status === 402 ? "Limite do plano atingido." : `Não foi possível concluir (HTTP ${response.status}).`))
  return payload as T
}

export type KnowledgeItem = { id: string; title: string; kind: "text" | "file" | "site"; source_url: string | null; enabled: boolean; size: number; preview: string; updated_at: string }
export type TeamMember = { subject: string; role: "owner" | "admin" | "operator" | "viewer"; role_label: string; email: string | null; display_name: string | null; approached: number; won: number; you: boolean }
export type TeamOverview = { members: TeamMember[]; ranking: TeamMember[]; invites: { id: string; email: string; role: string; role_label: string; expires_at: string }[]; seats: { used: number; limit: number }; can_manage: boolean }
export type PlanOverview = { plan: string; label: string; status: string; trial_ends_at: string | null; billing_connected: boolean
  usage: { metric: string; label: string; used: number; limit: number }[]; plans: { id: string; label: string; price_cents: number; limits: Record<string, number> }[] }
export type Preset = { id: string; label: string; offer: string; searches: string[] }

/** wa.me link with the message ready; Brazilian numbers without country code get 55. */
export function whatsappLink(text: string, whatsappUrl?: string | null, phone?: string | null): string | null {
  const fromUrl = whatsappUrl?.match(/(?:wa\.me\/|phone=)(\d{10,15})/)?.[1]
  let digits = fromUrl ?? (phone ?? "").replace(/\D/g, "")
  if (!digits || digits.length < 10) return null
  if (!fromUrl && (digits.length === 10 || digits.length === 11)) digits = `55${digits}`
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`
}
