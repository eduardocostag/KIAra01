export type ChatTransport = "cloud" | "local"
export type ChatMode = "chat" | "image" | "video" | "website" | "dashboard" | "automation"
export type ChatCapability = { id: string; available: boolean; detail: string }
export type ChatStatus = { connected: boolean; provider: string; model: string; capabilities: ChatCapability[] }
export type ChatMessage = { role: "user" | "assistant"; content: string }
export type ChatArtifact = { name: string; mime: "text/html"; content: string }
export type ChatPlan = { id: string; steps: string[]; requires_approval: true }
export type ChatVideoJob = { id: string; status: "running" | "done" | "failed"; progress: number; message: string; title: string; duration: number | null; warnings: string[]; error: string | null }
export type ChatReply = { text: string; provider?: string; model?: string; artifact?: ChatArtifact; plan?: ChatPlan; video?: ChatVideoJob }
export const CHAT_AUDIO_MAX_BYTES = 5 * 1024 * 1024
const audioTypes = new Set(["audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/aac", "audio/flac"])

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("O serviço retornou dados inválidos.")
  return value as Record<string, unknown>
}

export function parseChatStatus(value: unknown): ChatStatus {
  const data = object(value)
  if (typeof data.connected !== "boolean" || typeof data.provider !== "string" || typeof data.model !== "string" || !Array.isArray(data.capabilities)) throw new Error("Não foi possível confirmar as capacidades da Kiara.")
  const capabilities = data.capabilities.map((raw) => {
    const entry = object(raw)
    if (typeof entry.id !== "string" || typeof entry.available !== "boolean" || typeof entry.detail !== "string") throw new Error("O serviço retornou uma capacidade inválida.")
    return { id: entry.id, available: entry.available, detail: entry.detail }
  })
  return { connected: data.connected, provider: data.provider, model: data.model, capabilities }
}

export function parseChatReply(value: unknown): ChatReply {
  const data = object(value)
  if (typeof data.text !== "string" || !data.text.trim() || data.text.length > 150_000) throw new Error("A IA não retornou uma resposta válida.")
  const reply: ChatReply = { text: data.text }
  if (typeof data.provider === "string") reply.provider = data.provider
  if (typeof data.model === "string") reply.model = data.model
  if (data.artifact != null) {
    const artifact = object(data.artifact)
    if (artifact.mime !== "text/html" || typeof artifact.name !== "string" || typeof artifact.content !== "string" || artifact.content.length > 1_000_000) throw new Error("O arquivo gerado é inválido ou ultrapassou o limite.")
    reply.artifact = { name: artifact.name.replace(/[^\p{L}\p{N}._ -]/gu, "_").slice(0, 100) || "kiara-site.html", mime: "text/html", content: artifact.content }
  }
  if (data.plan != null) {
    const plan = object(data.plan)
    if (typeof plan.id !== "string" || !Array.isArray(plan.steps) || plan.steps.length > 30 || plan.requires_approval !== true) throw new Error("A tarefa não retornou um plano revisável.")
    const steps = plan.steps.map((step) => {
      if (typeof step === "string") return step
      const item = object(step)
      if (typeof item.title === "string") return item.title
      throw new Error("A tarefa retornou um passo inválido.")
    })
    reply.plan = { id: plan.id, steps, requires_approval: true }
  }
  if (data.video != null) reply.video = parseVideoJob(data.video)
  return reply
}

export function parseVideoJob(value: unknown): ChatVideoJob {
  const data = object(value)
  if (typeof data.id !== "string" || !/^[0-9a-f]{32}$/.test(data.id) || !["running", "queued", "done", "failed"].includes(String(data.status))) throw new Error("O serviço retornou uma tarefa de vídeo inválida.")
  return {
    id: data.id, status: data.status === "queued" ? "running" : data.status as ChatVideoJob["status"],
    progress: typeof data.progress === "number" ? Math.min(1, Math.max(0, data.progress)) : 0,
    message: typeof data.message === "string" ? data.message.slice(0, 200) : "", title: typeof data.title === "string" ? data.title.slice(0, 120) : "Vídeo",
    duration: typeof data.duration === "number" ? data.duration : null,
    warnings: Array.isArray(data.warnings) ? data.warnings.filter((item): item is string => typeof item === "string").slice(0, 10) : [],
    error: typeof data.error === "string" ? data.error.slice(0, 400) : null,
  }
}

/** Downloads a finished video from the local bridge (videos are produced on this computer). */
export async function fetchVideo(jobId: string): Promise<Blob> {
  const session = object(await jsonResponse(await fetch("/api/chat/session", { method: "POST", cache: "no-store" })))
  if (typeof session.access_token !== "string" || !session.access_token) throw new Error("Não foi possível autorizar o acesso ao serviço local.")
  const response = await fetch("http://127.0.0.1:3008/api/video", { method: "POST", mode: "cors", credentials: "omit", cache: "no-store", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify({ action: "download", job_id: jobId }), signal: AbortSignal.timeout(300_000) })
  if (!response.ok || response.headers.get("Content-Type") !== "video/mp4") { await jsonResponse(response); throw new Error("O vídeo não pôde ser baixado.") }
  return await response.blob()
}

export function validateChatAudio(file: Pick<File, "size" | "type">): string {
  const mime = file.type.split(";", 1)[0].toLowerCase()
  if (!audioTypes.has(mime)) throw new Error("Escolha um áudio WebM, OGG, WAV, MP3, M4A, AAC ou FLAC.")
  if (!file.size || file.size > CHAT_AUDIO_MAX_BYTES) throw new Error("O áudio deve ter conteúdo e no máximo 5 MB.")
  return mime
}

async function jsonResponse(response: Response): Promise<unknown> {
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const data = payload && typeof payload === "object" ? payload as Record<string, unknown> : null
    const error = data?.error
    const message = typeof error === "string" ? error : error && typeof error === "object" && "message" in error && typeof error.message === "string" ? error.message : typeof data?.detail === "string" ? data.detail : null
    throw new Error(message || (response.status === 401 ? "Sua sessão expirou. Entre novamente na Kiara." : `O serviço não concluiu a operação (HTTP ${response.status}).`))
  }
  if (!payload) throw new Error("O serviço retornou uma resposta vazia ou inválida.")
  return payload
}

export async function chatRequest(transport: ChatTransport, action: string, body: Record<string, unknown> = {}, signal?: AbortSignal): Promise<unknown> {
  const timeout = AbortSignal.timeout(action === "status" ? 15_000 : 180_000)
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  try {
    if (transport === "cloud") {
      const endpoint = action === "chat" ? "messages" : action
      return await jsonResponse(await fetch(`/api/chat/${endpoint}`, { method: action === "status" ? "GET" : "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, ...(action === "status" ? {} : { body: JSON.stringify(body) }), signal: requestSignal }))
    }
    const session = object(await jsonResponse(await fetch("/api/chat/session", { method: "POST", cache: "no-store", signal: requestSignal })))
    if (typeof session.access_token !== "string" || !session.access_token) throw new Error("Não foi possível autorizar o acesso ao serviço local.")
    return await jsonResponse(await fetch(`http://127.0.0.1:3008/api/${action}`, { method: "POST", mode: "cors", credentials: "omit", cache: "no-store", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify(body), signal: requestSignal }))
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Operação interrompida.", "AbortError")
    if (error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name)) throw new Error("O serviço ultrapassou o tempo de resposta. Confira a conexão e tente novamente.")
    if (error instanceof TypeError) throw new Error(transport === "local" ? "O serviço local da Kiara não respondeu. Inicie a ponte neste computador e permita o acesso à rede local no navegador." : "Não foi possível conectar à IA. Verifique a conexão e tente novamente.")
    throw error
  }
}

export function isolatedHtml(content: string): string {
  const csp = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-src 'none'; media-src data: blob:"
  return `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="${csp}"></head><body>${content}</body></html>`
}

export function blobBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result.split(",")[1]) : reject(new Error("Não foi possível ler o áudio."))
    reader.onerror = () => reject(new Error("Não foi possível ler o áudio."))
    reader.readAsDataURL(blob)
  })
}
