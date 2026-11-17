export type ChatTransport = "cloud" | "local"
export type ChatMode = "chat" | "image" | "video" | "website" | "dashboard" | "automation"
export type ChatCapability = { id: string; available: boolean; detail: string }
export type ChatStatus = { connected: boolean; provider: string; model: string; capabilities: ChatCapability[] }
/** `file_context` and `attachments` carry what was attached to an earlier message, so later turns can still use it. */
export type ChatMessage = { role: "user" | "assistant"; content: string; file_context?: string; attachments?: { name: string; mime: ChatAttachment["mime"]; data_base64: string }[] }
export type ChatArtifact = { name: string; mime: "text/html"; content: string }
export type ChatPlan = { id: string; steps: string[]; requires_approval: true }
export type ChatVideoJob = { id: string; status: "running" | "done" | "failed"; progress: number; message: string; title: string; duration: number | null; warnings: string[]; error: string | null }
/** `src` is a data URL; `thumb` is the small copy kept in this browser's history. */
export type ChatImage = { src: string; prompt: string; thumb?: string }
export type ChatSource = { title: string; url: string; site: string }
const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
export type ChatAttachment = { name: string; mime: "image/jpeg" | "image/png" | "image/webp" | "application/pdf" | typeof DOCX | typeof XLSX | "text/csv" | "text/plain"; data_base64: string; kind: "image" | "pdf" | "document" | "sheet"; preview?: string }
/** A site or app Kiara opens for the person ("abra o youtube"). Only https and a few app links are accepted. */
export type ChatAction = { label: string; url: string }
export type ChatReply = { text: string; provider?: string; model?: string; artifact?: ChatArtifact; plan?: ChatPlan; video?: ChatVideoJob; image?: ChatImage; sources?: ChatSource[]; actions?: ChatAction[]; file_context?: string }
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
  if (data.image != null) reply.image = parseChatImage(data.image)
  if (Array.isArray(data.sources)) reply.sources = parseSources(data.sources)
  if (Array.isArray(data.actions)) reply.actions = parseActions(data.actions)
  if (typeof data.file_context === "string" && data.file_context.trim()) reply.file_context = data.file_context.slice(0, 20_000)
  return reply
}

const ACTION_URL = /^(https:\/\/|vscode:\/\/|obsidian:\/\/|microsoft-edge:https:\/\/)/

export function parseActions(values: unknown[]): ChatAction[] {
  return values.flatMap((value) => {
    if (!value || typeof value !== "object") return []
    const item = value as Record<string, unknown>
    return typeof item.url === "string" && typeof item.label === "string" && ACTION_URL.test(item.url) && item.url.length <= 600
      ? [{ url: item.url, label: item.label.slice(0, 60) }] : []
  }).slice(0, 3)
}

function parseSources(values: unknown[]): ChatSource[] {
  return values.flatMap((value) => {
    if (!value || typeof value !== "object") return []
    const item = value as Record<string, unknown>
    const url = typeof item.url === "string" && /^https?:\/\//.test(item.url) ? item.url : ""
    return url ? [{ url, title: String(item.title || item.site || url).slice(0, 160), site: String(item.site || new URL(url).hostname).slice(0, 80) }] : []
  }).slice(0, 6)
}

export type StreamEvent = { type: "delta"; text: string } | { type: "reset" } | { type: "status"; text: string }

/** Thrown when the streaming route is not usable at all, so the caller can use the classic request. */
export class StreamUnavailableError extends Error {}

/** The chat answer while it is written. Resolves with the final reply; partial text arrives through `onEvent`. */
export async function streamChat(body: Record<string, unknown>, onEvent: (event: StreamEvent) => void, signal?: AbortSignal): Promise<ChatReply> {
  const timeout = AbortSignal.timeout(300_000)
  const response = await fetch("/api/chat/stream", { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: signal ? AbortSignal.any([signal, timeout]) : timeout })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    const message = (payload as { error?: { message?: string } } | null)?.error?.message
    if (response.status === 422 || response.status === 413) throw new Error(message || "Não foi possível enviar os anexos.")
    throw new StreamUnavailableError(message || `HTTP ${response.status}`)
  }
  if (!response.body || !(response.headers.get("content-type") ?? "").includes("text/event-stream")) throw new StreamUnavailableError("sem stream")
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    let boundary = buffer.indexOf("\n\n")
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf("\n\n")
      const line = chunk.split("\n").find((item) => item.startsWith("data:"))
      if (!line) continue
      const event = JSON.parse(line.slice(5)) as Record<string, unknown>
      if (event.type === "delta" && typeof event.text === "string") onEvent({ type: "delta", text: event.text })
      else if (event.type === "reset") onEvent({ type: "reset" })
      else if (event.type === "status" && typeof event.text === "string") onEvent({ type: "status", text: event.text })
      else if (event.type === "error") throw new Error(typeof event.message === "string" ? event.message : "Não foi possível concluir a resposta.")
      else if (event.type === "done") return parseChatReply({ ...event, provider: "kiara" })
    }
    if (done) break
  }
  throw new Error("A resposta foi interrompida. Tente de novo.")
}

export const CHAT_ATTACHMENT_LIMIT = 3 * 1024 * 1024
export const CHAT_ATTACHMENT_ACCEPT = "image/jpeg,image/png,image/webp,application/pdf,.pdf,.docx,.xlsx,.csv,.txt,.md," + DOCX + "," + XLSX + ",text/csv,text/plain"
// Browsers report spreadsheets and CSVs inconsistently (Windows often says "application/vnd.ms-excel" for .csv), so the extension decides.
const DOCUMENTS: Record<string, { mime: ChatAttachment["mime"]; kind: ChatAttachment["kind"]; label: string }> = {
  pdf: { mime: "application/pdf", kind: "pdf", label: "O PDF" }, docx: { mime: DOCX, kind: "document", label: "O documento" },
  xlsx: { mime: XLSX, kind: "sheet", label: "A planilha" }, csv: { mime: "text/csv", kind: "sheet", label: "A planilha" },
  txt: { mime: "text/plain", kind: "document", label: "O arquivo" }, md: { mime: "text/plain", kind: "document", label: "O arquivo" },
}

/** Photos are resized in the browser (at most 1600 px, JPEG) so several fit in one message; documents go as they are. */
export async function prepareAttachment(file: File): Promise<ChatAttachment> {
  const mime = file.type.toLowerCase()
  const extension = file.name.toLowerCase().split(".").pop() ?? ""
  if (extension === "doc" || extension === "xls") throw new Error(`Esse formato antigo (.${extension}) não é aceito. Salve como .${extension}x e anexe de novo.`)
  const known = DOCUMENTS[extension] ?? (mime === "application/pdf" ? DOCUMENTS.pdf : undefined)
  if (known) {
    if (file.size > CHAT_ATTACHMENT_LIMIT) throw new Error(`${known.label} pode ter no máximo 3 MB.`)
    return { name: file.name.slice(0, 200), mime: known.mime, kind: known.kind, data_base64: await blobBase64(file) }
  }
  if (!mime.startsWith("image/")) throw new Error("Anexe uma foto, um PDF, um documento Word (.docx), uma planilha (.xlsx ou .csv) ou um arquivo de texto.")
  const url = URL.createObjectURL(file)
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image()
      element.onload = () => resolve(element)
      element.onerror = () => reject(new Error("Não consegui abrir essa imagem."))
      element.src = url
    })
    const draw = (side: number, quality: number) => {
      const scale = Math.min(1, side / Math.max(image.naturalWidth, image.naturalHeight))
      const canvas = document.createElement("canvas")
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
      canvas.getContext("2d")?.drawImage(image, 0, 0, canvas.width, canvas.height)
      return canvas.toDataURL("image/jpeg", quality)
    }
    const full = draw(1600, 0.85)
    return { name: file.name.slice(0, 200) || "foto.jpg", mime: "image/jpeg", kind: "image", data_base64: full.split(",")[1], preview: draw(160, 0.7) }
  } finally { URL.revokeObjectURL(url) }
}

export function parseChatImage(value: unknown): ChatImage {
  const data = object(value)
  if (!["image/jpeg", "image/png", "image/webp"].includes(String(data.mime)) || typeof data.data_base64 !== "string"
    || !data.data_base64 || data.data_base64.length > 6_000_000 || !/^[A-Za-z0-9+/]+={0,2}$/.test(data.data_base64)) throw new Error("A imagem gerada é inválida.")
  return { src: `data:${data.mime};base64,${data.data_base64}`, prompt: typeof data.prompt === "string" ? data.prompt.slice(0, 500) : "" }
}

/** A small JPEG copy (about 30 KB) so the picture survives in the browser's limited history storage. */
export function imageThumbnail(src: string, side = 384): Promise<string> {
  return new Promise((resolve) => {
    const image = new Image()
    image.onload = () => {
      const scale = Math.min(1, side / Math.max(image.naturalWidth, image.naturalHeight))
      const canvas = document.createElement("canvas")
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
      const context = canvas.getContext("2d")
      if (!context) return resolve("")
      context.drawImage(image, 0, 0, canvas.width, canvas.height)
      try { resolve(canvas.toDataURL("image/jpeg", 0.72)) } catch { resolve("") }
    }
    image.onerror = () => resolve("")
    image.src = src
  })
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

/**
 * Where the Kiara server (chat, voice and videos) answers. Defaults to this computer; set
 * NEXT_PUBLIC_KIARA_CHAT_URL to the always-on server (e.g. https://kiara.example.com).
 * Only HTTPS, or plain HTTP on loopback, is accepted.
 */
export function chatServerUrl(value = process.env.NEXT_PUBLIC_KIARA_CHAT_URL): string {
  const fallback = "http://127.0.0.1:3008"
  if (!value) return fallback
  try {
    const url = new URL(value)
    const loopback = ["127.0.0.1", "localhost"].includes(url.hostname)
    if (url.username || url.password || url.search || url.hash || !(url.protocol === "https:" || (url.protocol === "http:" && loopback))) return fallback
    return url.origin + url.pathname.replace(/\/+$/, "")
  } catch {
    return fallback
  }
}

/** Downloads a finished video from the local bridge (videos are produced on this computer). */
export async function fetchVideo(jobId: string, transport: ChatTransport = "local"): Promise<Blob> {
  if (transport === "cloud") {
    // Kiara's server keeps the finished clip (at most 3 MB); it arrives as base64 inside JSON.
    const payload = object(await chatRequest("cloud", "video", { action: "download", job_id: jobId }))
    if (payload.mime !== "video/mp4" || typeof payload.data_base64 !== "string" || !payload.data_base64) throw new Error("O vídeo não pôde ser baixado.")
    const bytes = Uint8Array.from(atob(payload.data_base64), (char) => char.charCodeAt(0))
    return new Blob([bytes], { type: "video/mp4" })
  }
  const session = object(await jsonResponse(await fetch("/api/chat/session", { method: "POST", cache: "no-store" })))
  if (typeof session.access_token !== "string" || !session.access_token) throw new Error("Não foi possível autorizar o acesso ao serviço local.")
  const response = await fetch(`${chatServerUrl()}/api/video`, { method: "POST", mode: "cors", credentials: "omit", cache: "no-store", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify({ action: "download", job_id: jobId }), signal: AbortSignal.timeout(300_000) })
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
  // A chat turn may try several providers (up to 240 s) and then draw a picture.
  const timeout = AbortSignal.timeout(action === "status" ? 15_000 : 300_000)
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  try {
    if (transport === "cloud") {
      const endpoint = action === "chat" ? "messages" : action
      return await jsonResponse(await fetch(`/api/chat/${endpoint}`, { method: action === "status" ? "GET" : "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, ...(action === "status" ? {} : { body: JSON.stringify(body) }), signal: requestSignal }))
    }
    const session = object(await jsonResponse(await fetch("/api/chat/session", { method: "POST", cache: "no-store", signal: requestSignal })))
    if (typeof session.access_token !== "string" || !session.access_token) throw new Error("Não foi possível autorizar o acesso ao serviço local.")
    return await jsonResponse(await fetch(`${chatServerUrl()}/api/${action}`, { method: "POST", mode: "cors", credentials: "omit", cache: "no-store", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify(body), signal: requestSignal }))
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Operação interrompida.", "AbortError")
    if (error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name)) throw new Error("O serviço ultrapassou o tempo de resposta. Confira a conexão e tente novamente.")
    if (error instanceof TypeError) throw new Error(transport === "local" ? process.env.NEXT_PUBLIC_KIARA_CHAT_URL ? "O servidor da Kiara não respondeu. Confira se ele está ligado e conectado à internet." : "O serviço local da Kiara não respondeu. Inicie a ponte neste computador e permita o acesso à rede local no navegador." : "Não foi possível conectar à IA. Verifique a conexão e tente novamente.")
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
