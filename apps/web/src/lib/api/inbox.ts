import "server-only"

import { auth } from "@clerk/nextjs/server"

import { requireWorkspace } from "@/lib/auth"

export type InboxMessageDTO = Readonly<{
  id: string
  from: "lead" | "operator"
  text: string
  time: string
}>

export type InboxConversationDTO = Readonly<{
  id: string
  name: string
  handle: string
  excerpt: string
  time: string
  unread: number
  status: string
  score: number
  messages: readonly InboxMessageDTO[]
  intent: string
  confidence: string
  owner: string
  qualifiedAt: string | null
  facts: readonly string[]
  gaps: readonly string[]
  nextAction: string
  suggestedDraft: string
  savedDraft: Readonly<{ text: string; status: "draft" | "approved" | "invalidated" }> | null
}>

export type InboxViewDTO = Readonly<{
  source: "api"
  conversations: readonly InboxConversationDTO[]
}>

export class KiaraApiError extends Error {
  constructor(message: string, readonly correlationId: string) {
    super(message)
    this.name = "KiaraApiError"
  }
}

type JsonObject = Record<string, unknown>

function object(value: unknown, field: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`Invalid ${field}`)
  return value as JsonObject
}

function string(value: unknown, field: string, max = 4_000): string {
  if (typeof value !== "string" || !value || value.length > max) throw new Error(`Invalid ${field}`)
  return value
}

function integer(value: unknown, field: string, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) throw new Error(`Invalid ${field}`)
  return value as number
}

function timestamp(value: unknown, field: string): string {
  const parsed = string(value, field, 64)
  if (Number.isNaN(Date.parse(parsed))) throw new Error(`Invalid ${field}`)
  return parsed
}

function apiUrl(): string {
  const configured = process.env.KIARA_API_URL?.trim()
  if (!configured) throw new KiaraApiError("A API da Kiara não está configurada.", crypto.randomUUID())
  const parsed = new URL(configured)
  if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("KIARA_API_URL must use HTTP(S)")
  if (process.env.KIARA_DEPLOYMENT_ENV === "production" && parsed.protocol !== "https:") throw new Error("KIARA_API_URL must use HTTPS in production")
  return parsed.toString().replace(/\/$/, "")
}

function timeoutMs(): number {
  const parsed = Number(process.env.KIARA_API_TIMEOUT_MS ?? "5000")
  return Number.isInteger(parsed) && parsed >= 500 && parsed <= 30_000 ? parsed : 5_000
}

async function apiGet(path: string, token: string): Promise<unknown> {
  const correlationId = crypto.randomUUID()
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs())
  try {
    const protectionBypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET?.trim()
    const response = await fetch(`${apiUrl()}${path}`, {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Correlation-ID": correlationId,
        ...(protectionBypass ? { "x-vercel-protection-bypass": protectionBypass } : {}),
      },
      signal: controller.signal,
    })
    const responseCorrelation = response.headers.get("x-correlation-id") ?? correlationId
    if (!response.ok) throw new KiaraApiError("Não foi possível consultar a Inbox.", responseCorrelation)
    return await response.json()
  } catch (error) {
    if (error instanceof KiaraApiError) throw error
    throw new KiaraApiError("A API da Kiara está indisponível no momento.", correlationId)
  } finally {
    clearTimeout(timeout)
  }
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value))
}

const statusLabels: Record<string, string> = {
  open: "Nova",
  waiting_customer: "Aguardando cliente",
  waiting_operator: "Aprovação",
  resolved: "Concluída",
}

function parseDetail(value: unknown): InboxConversationDTO {
  const item = object(value, "thread")
  const consumer = object(item.consumer, "consumer")
  if (!Array.isArray(item.messages)) throw new Error("Invalid messages")
  if (!Array.isArray(item.drafts)) throw new Error("Invalid drafts")

  const messages = item.messages.map((raw): InboxMessageDTO => {
    const message = object(raw, "message")
    const direction = string(message.direction, "message.direction", 16)
    if (direction !== "inbound" && direction !== "outbound") throw new Error("Invalid message.direction")
    return {
      id: string(message.id, "message.id", 64),
      from: direction === "inbound" ? "lead" : "operator",
      text: string(message.text, "message.text"),
      time: formatTime(timestamp(message.created_at, "message.created_at")),
    }
  })

  const drafts: Array<NonNullable<InboxConversationDTO["savedDraft"]>> = item.drafts.map((raw) => {
    const draft = object(raw, "draft")
    const status = string(draft.status, "draft.status", 16)
    if (status !== "draft" && status !== "approved" && status !== "invalidated") throw new Error("Invalid draft.status")
    return { text: string(draft.text, "draft.text", 1_000), status }
  })
  const latestDraft = drafts.at(-1) ?? null
  const qualification = item.qualification == null ? null : object(item.qualification, "qualification")
  const score = qualification ? integer(qualification.score, "qualification.score", 0, 100) : 0
  const recommendation = qualification
    ? string(qualification.recommendation, "qualification.recommendation", 1_000)
    : "Revisar a conversa antes de preparar uma resposta."
  const username = string(consumer.instagram_username, "consumer.instagram_username", 64)

  return {
    id: string(item.id, "thread.id", 64),
    name: string(consumer.display_name, "consumer.display_name", 120),
    handle: `@${username.replace(/^@/, "")}`,
    excerpt: messages.at(-1)?.text ?? "Sem mensagens",
    time: formatTime(timestamp(item.updated_at, "thread.updated_at")),
    unread: integer(item.unread_count, "thread.unread_count"),
    status: statusLabels[string(item.status, "thread.status", 32)] ?? "Em atendimento",
    score,
    messages,
    intent: qualification ? "Intenção ainda não detalhada pela API" : "Ainda não qualificada",
    confidence: "Não informada",
    owner: "Não informado",
    qualifiedAt: qualification ? formatTime(timestamp(qualification.created_at, "qualification.created_at")) : null,
    facts: [],
    gaps: [],
    nextAction: recommendation,
    suggestedDraft: latestDraft?.text ?? "",
    savedDraft: latestDraft,
  }
}

export async function getInboxDTO(): Promise<InboxViewDTO> {
  await requireWorkspace()

  const session = await auth()
  const token = await session.getToken()
  if (!token) throw new KiaraApiError("A sessão não forneceu acesso à API.", crypto.randomUUID())
  const page = object(await apiGet("/v1/inbox/threads", token), "thread page")
  if (!Array.isArray(page.items)) throw new KiaraApiError("A API retornou uma resposta inválida.", crypto.randomUUID())

  try {
    const conversations = await Promise.all(page.items.map(async (summary) => {
      const id = string(object(summary, "thread summary").id, "thread.id", 64)
      return parseDetail(await apiGet(`/v1/inbox/threads/${encodeURIComponent(id)}`, token))
    }))
    return { source: "api", conversations }
  } catch (error) {
    if (error instanceof KiaraApiError) throw error
    throw new KiaraApiError("A API retornou dados incompatíveis.", crypto.randomUUID())
  }
}
