import "server-only"

import { requireAccessToken, requireWorkspace } from "@/lib/auth"

export type { InboxMessageDTO, InboxConversationDTO } from "./inbox-contract"
import { parseInboxDetail, type InboxConversationDTO } from "./inbox-contract"

export type InboxViewDTO = Readonly<{
  source: "api"
  conversations: readonly InboxConversationDTO[]
  canSend: boolean
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

export async function getInboxDTO(): Promise<InboxViewDTO> {
  await requireWorkspace()

  const token = await requireAccessToken()
  const page = object(await apiGet("/v1/inbox/threads", token), "thread page")
  const identity = await apiGet("/v1/me", token).then(value => object(value, "identity")).catch(() => ({} as JsonObject))
  const canSend = Array.isArray(identity.capabilities) && identity.capabilities.includes("outbound.approve")
  if (!Array.isArray(page.items)) throw new KiaraApiError("A API retornou uma resposta inválida.", crypto.randomUUID())

  try {
    const conversations = await Promise.all(page.items.map(async (summary) => {
      const id = string(object(summary, "thread summary").id, "thread.id", 64)
      return parseInboxDetail(await apiGet(`/v1/inbox/threads/${encodeURIComponent(id)}`, token))
    }))
    return { source: "api", conversations, canSend }
  } catch (error) {
    if (error instanceof KiaraApiError) throw error
    throw new KiaraApiError("A API retornou dados incompatíveis.", crypto.randomUUID())
  }
}
