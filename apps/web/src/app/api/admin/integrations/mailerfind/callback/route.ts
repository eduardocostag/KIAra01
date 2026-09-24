import { cookies } from "next/headers"
import { requireSystemAdmin } from "@/lib/auth"
import { kiaraApi } from "@/lib/api/server-client"
import { MAILERFIND_COOKIE, MAILERFIND_ISSUER, MAILERFIND_MCP_URL, openOAuthState } from "@/lib/mailerfind/oauth"

type TokenResponse = {
  access_token?: string
  refresh_token?: string
  expires_in?: number
  scope?: string
  token_type?: string
}

type ConnectionResult = "connected" | "denied" | "state_error" | "token_error" | "validation_error" | "save_error" | "error"

function resultRedirect(origin: string, result: ConnectionResult) {
  return Response.redirect(`${origin}/app/admin?mailerfind=${result}`)
}

export async function GET(request: Request) {
  const url = new URL(request.url)
  const cookieStore = await cookies()
  const sealed = cookieStore.get(MAILERFIND_COOKIE)?.value
  cookieStore.delete(MAILERFIND_COOKIE)
  let stage: Exclude<ConnectionResult, "connected" | "denied" | "error"> = "state_error"
  try {
    await requireSystemAdmin()
    if (url.searchParams.get("error")) return resultRedirect(url.origin, "denied")
    const code = url.searchParams.get("code")
    const returnedState = url.searchParams.get("state")
    if (!sealed || !code || !returnedState) throw new Error("Resposta OAuth incompleta.")
    const state = openOAuthState(sealed)
    if (state.state !== returnedState || Date.now() - state.createdAt > 10 * 60_000) throw new Error("Estado OAuth expirado.")

    stage = "token_error"
    const tokenBody = new URLSearchParams({
      grant_type: "authorization_code", code, redirect_uri: state.redirectUri,
      client_id: state.clientId, code_verifier: state.verifier,
    })
    if (state.clientSecret) tokenBody.set("client_secret", state.clientSecret)
    const tokenResponse = await fetch(`${MAILERFIND_ISSUER}token`, {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: tokenBody, signal: AbortSignal.timeout(12_000),
    })
    const token = await tokenResponse.json() as TokenResponse
    if (!tokenResponse.ok || !token.access_token) throw new Error("O MailerFind não entregou um token válido.")

    stage = "validation_error"
    const check = await fetch(MAILERFIND_MCP_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token.access_token}`,
        Accept: "application/json, text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: "kiara-connect", method: "initialize", params: {
        protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "Kiara", version: "1.0" },
      } }),
      signal: AbortSignal.timeout(12_000),
    })
    if (!check.ok) throw new Error(`A validação MCP retornou HTTP ${check.status}.`)

    const credentials = {
      endpoint_url: MAILERFIND_MCP_URL,
      access_token: token.access_token,
      client_id: state.clientId,
      ...(state.clientSecret ? { client_secret: state.clientSecret } : {}),
      ...(token.refresh_token ? { refresh_token: token.refresh_token } : {}),
      ...(token.scope ? { scope: token.scope } : {}),
      token_type: token.token_type || "Bearer",
      ...(typeof token.expires_in === "number" ? { expires_at: new Date(Date.now() + token.expires_in * 1000).toISOString() } : {}),
    }
    stage = "save_error"
    const saved = await kiaraApi("/v1/integrations/mailerfind/global", { method: "PUT", body: JSON.stringify({ credentials }) })
    if (!saved.ok) {
      const payload = await saved.json().catch(() => null) as { error?: { code?: string; request_id?: string } } | null
      console.error(JSON.stringify({
        level: "error",
        event: "mailerfind.oauth_save_failed",
        upstream_status: saved.status,
        upstream_code: payload?.error?.code,
        request_id: payload?.error?.request_id,
      }))
      throw new Error("A conexão foi autorizada, mas não pôde ser guardada no cofre da Kiara.")
    }
    console.log(JSON.stringify({ level: "info", event: "mailerfind.oauth_connected", scope: token.scope ?? null }))
    return resultRedirect(url.origin, "connected")
  } catch (error) {
    console.error(JSON.stringify({
      level: "error",
      event: "mailerfind.oauth_failed",
      stage,
      error_class: error instanceof Error ? error.name : "UnknownError",
      message: error instanceof Error ? error.message.slice(0, 240) : "Falha desconhecida",
    }))
    return resultRedirect(url.origin, stage)
  }
}
