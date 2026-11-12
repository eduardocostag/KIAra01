/** Browser-side client for the WhatsApp Web executor (Kiara extension + local executor). */

export type WhatsAppContact = { phone: string; name: string; enabled: boolean; handoff: boolean }
export type WhatsAppConfig = {
  pilot_mode: boolean; daily_limit?: number; auto_reply_enabled?: boolean; followup_enabled?: boolean
  initial_outreach_enabled?: boolean; outreach_template?: string; pilot_consent_confirmed: boolean; enabled: boolean
  ai_context: string; reply_template: string; followup_template: string; followup_hours: number
  contact_start: string; contact_end: string; contacts: WhatsAppContact[]
}
export type WhatsAppActivity = { id: string; phone: string; kind: string; text: string; occurred_at: string; status: string }
export type WhatsAppEvents = { items: WhatsAppActivity[]; last_heartbeat_at: string | null; online: boolean }
export type WhatsAppAnalysisJob = { id: string; status: "queued" | "running" | "completed" | "failed"; result?: { imported?: number; duplicates?: number; scanned?: number; skipped?: number; error?: string | null } | null }

function apiErrorMessage(payload: unknown) {
  if (typeof payload !== "object" || payload === null || !("error" in payload)) return null
  const error = payload.error
  return typeof error === "object" && error !== null && "message" in error && typeof error.message === "string" ? error.message : null
}

export async function whatsappWebRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/whatsapp-web/${path}`, { ...init, cache: "no-store", headers: { "Content-Type": "application/json" }, signal: init?.signal ?? AbortSignal.timeout(15000) })
  const text = await response.text()
  let payload: unknown
  try { payload = JSON.parse(text) } catch {
    throw new Error(/^\s*</.test(text) ? "Não foi possível carregar o WhatsApp. Tente novamente em instantes." : "A conexão não respondeu como esperado. Tente novamente.")
  }
  if (!response.ok) throw new Error(apiErrorMessage(payload) ?? "Não foi possível acessar o WhatsApp.")
  return payload as T
}

/** Asks the Kiara extension to open/prepare the logged-in WhatsApp Web tab in this Chrome. */
export function prepareWhatsAppWeb() {
  const requestId = crypto.randomUUID()
  return new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      window.removeEventListener("message", handleMessage)
      reject(new Error("Extensão Kiara não encontrada. Instale-a no Chrome e recarregue esta página e o WhatsApp Web."))
    }, 45000)
    function handleMessage(event: MessageEvent) {
      if (event.source !== window || event.origin !== window.location.origin) return
      if (event.data?.source !== "kiara-whatsapp-extension" || event.data.type !== "whatsapp-ready" || event.data.requestId !== requestId) return
      clearTimeout(timeout)
      window.removeEventListener("message", handleMessage)
      if (event.data.error) reject(new Error(event.data.error))
      else resolve()
    }
    window.addEventListener("message", handleMessage)
    window.postMessage({ source: "kiara-app", type: "whatsapp-prepare", requestId }, window.location.origin)
  })
}

/** Waits until the local executor reports a heartbeat to the site. */
export async function waitForWhatsAppExecutor() {
  const deadline = Date.now() + 90000
  while (Date.now() < deadline) {
    if ((await whatsappWebRequest<WhatsAppEvents>("events")).online) return
    await new Promise((resolve) => setTimeout(resolve, 3000))
  }
  throw new Error("Não foi possível conectar. Mantenha a Kiara e o WhatsApp Web abertos no mesmo Chrome e tente novamente.")
}

/** Full connect flow: wake the executor, prepare WhatsApp Web, wait for its heartbeat. */
export async function connectWhatsAppWeb() {
  // Wakes the installed executor via its protocol handler. Unlike window.open, an
  // unregistered protocol is ignored instead of leaving a blank tab behind.
  const link = document.createElement("a")
  link.href = "kiara-whatsapp://analyze"
  link.click()
  await prepareWhatsAppWeb()
  await waitForWhatsAppExecutor()
}
