export const templateLabels: Record<string, string> = {
  first_contact: "Primeiro contato", no_website: "Sem site informado", website_opportunity: "Oportunidade no site",
  instagram_opportunity: "Instagram", follow_up: "Follow-up", reactivation: "Reativação", objection: "Objeção", interest: "Demonstrou interesse",
}
export type SalesProfile = { business_name: string; sender_name: string; offer: string; tone: string; follow_up_hours: number; contact_start: string; contact_end: string; templates: Record<string, string>; updated_at: string | null }
export type OutreachActivity = { id: string; channel: "whatsapp" | "instagram" | "phone"; status: "opened" | "sent" | "replied" | "no_response"; body: string; next_follow_up_at: string | null; created_at: string }
export async function salesRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...init, cache: "no-store", headers: { "Content-Type": "application/json", ...init.headers } })
  let payload: T & { error?: { code?: string; message?: string; request_id?: string }; detail?: Array<{ loc?: Array<string | number>; msg?: string }> }
  try { payload = await response.json() } catch { throw new Error("O servidor retornou uma resposta inválida.") }
  if (!response.ok) {
    const validation = Array.isArray(payload.detail) ? payload.detail.find((item) => typeof item?.msg === "string") : null
    const field = validation?.loc?.at(-1)
    const diagnostic = [
      payload.error?.code ? `Código: ${payload.error.code}` : "",
      payload.error?.request_id ? `ID: ${payload.error.request_id}` : "",
    ].filter(Boolean).join(" · ")
    const message = payload.error?.message || (validation?.msg ? `A API recusou ${field ? `o campo “${field}”` : "os dados"}: ${validation.msg}` : `Não foi possível concluir a operação (HTTP ${response.status}).`)
    throw new Error(diagnostic ? `${message} ${diagnostic}` : message)
  }
  return payload
}
