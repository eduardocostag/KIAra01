import "server-only"
import { AdministratorRequiredError, AuthenticationRequiredError, requireAccessToken, requireSystemAdmin, requireWorkspace } from "@/lib/auth"
import { moduleForApiPath } from "@/lib/modules"

type ApiErrorPayload = {
  error: { code: string; message: string; request_id: string; details?: Record<string, unknown> }
}

function errorResponse(status: number, code: string, message: string, requestId: string, details?: Record<string, unknown>) {
  return Response.json({ error: { code, message, request_id: requestId, ...(details ? { details } : {}) } } satisfies ApiErrorPayload, {
    status,
    headers: { "Cache-Control": "no-store", "X-Correlation-ID": requestId },
  })
}

function upstreamFormatError(status: number, contentType: string, requestId: string) {
  if (status === 401 || status === 403) return errorResponse(502, "upstream_auth_rejected", "A API recusou a autenticação enviada pelo site. Verifique a configuração Supabase/OIDC do backend.", requestId, { upstream_status: status })
  if (status === 404) return errorResponse(502, "upstream_route_not_found", "A rota da API não foi encontrada. Verifique se KIARA_API_URL aponta para o backend correto.", requestId, { upstream_status: status })
  if (status === 412) return errorResponse(412, "version_conflict", "Este lead foi atualizado depois que a página foi carregada.", requestId, { upstream_status: status })
  if (status >= 500) return errorResponse(502, "upstream_server_error", "A API falhou internamente (HTTP " + status + ") e não devolveu o diagnóstico esperado.", requestId, { upstream_status: status })
  return errorResponse(502, "upstream_invalid_response", "A API respondeu em formato inválido (" + (contentType || "tipo não informado") + ", HTTP " + status + "). KIARA_API_URL pode estar apontando para uma página em vez do backend.", requestId, { upstream_status: status })
}

/** `stream`: pass a server-sent event stream through as it arrives (the chat answer being written).
 *  `video`: pass an MP4 body through untouched (a part of a finished video). */
export async function kiaraApi(path: string, init: RequestInit = {}, options: { stream?: boolean; video?: boolean } = {}) {
  const requestId = crypto.randomUUID()
  const startedAt = Date.now()
  const method = init.method ?? "GET"
  const log = (level: "info" | "warn" | "error", event: string, data: Record<string, unknown> = {}) => {
    const entry = { level, event, route: path, method, request_id: requestId, duration_ms: Date.now() - startedAt, ...data }
    if (level === "error") console.error(JSON.stringify(entry))
    else if (level === "warn") console.warn(JSON.stringify(entry))
    else console.log(JSON.stringify(entry))
  }

  let token: string
  try {
    if (path === "/v1/integrations" || path.startsWith("/v1/integrations/") || path.startsWith("/v1/sdr/")) await requireSystemAdmin()
    // Chat, WhatsApp and Automation routes only reach the backend for accounts the administrator gave that module.
    const routeModule = moduleForApiPath(path)
    if (routeModule && !(await requireWorkspace()).modules.includes(routeModule)) {
      return errorResponse(403, "module_not_enabled", "Este módulo não está liberado para sua conta. Fale com o administrador.", requestId)
    }
    token = await requireAccessToken()
  } catch (error) {
    if (error instanceof AdministratorRequiredError) return errorResponse(403, "system_admin_required", "Acesso exclusivo do administrador.", requestId)
    if (!(error instanceof AuthenticationRequiredError)) throw error
    log("error", "kiara_api.session_missing")
    return errorResponse(401, "session_missing", "Sua sessão não forneceu um token válido. Entre novamente na Kiara.", requestId)
  }

  const isCompetitionRoute = path.startsWith("/v1/competition/")
  const configuredBase = (
    isCompetitionRoute
      ? process.env.KIARA_COMPETITION_API_URL
      : process.env.KIARA_API_URL
  )?.trim()
  const configurationName = isCompetitionRoute
    ? "KIARA_COMPETITION_API_URL"
    : "KIARA_API_URL"
  if (!configuredBase) {
    log("error", "kiara_api.not_configured", { configuration: configurationName })
    return errorResponse(503, "api_not_configured", `A conexão com o backend não está configurada. Cadastre ${configurationName} na Vercel.`, requestId)
  }

  let target: URL
  try {
    const base = new URL(configuredBase)
    if (!["http:", "https:"].includes(base.protocol)) throw new Error("unsupported protocol")
    target = new URL(path, base.href.endsWith("/") ? base.href : base.href + "/")
  } catch {
    log("error", "kiara_api.invalid_url")
    return errorResponse(503, "api_url_invalid", "KIARA_API_URL não é uma URL HTTP(S) válida. Corrija a variável de ambiente na Vercel.", requestId)
  }

  const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET?.trim()
  const timeoutMs = path === "/v1/chat/messages" || path === "/v1/chat/stream" ? 285_000 : path === "/v1/chat/image" ? 150_000 : path === "/v1/chat/video" ? 100_000 : path === "/v1/chat/speech" ? 40_000 : path === "/v1/sdr/simulate" ? 90_000 : path === "/v1/whatsapp-server/sync" ? 55_000 : path === "/v1/whatsapp-official/connect" ? 55_000 : path.startsWith("/v1/inbox/threads/") && path.endsWith("/messages") ? 45_000 : path.startsWith("/v1/leads/") && path.endsWith("/company") ? 60_000 : path.endsWith("/confirm") || path.endsWith("/process")
    ? 290_000
    : path.startsWith("/v1/competition/kiara/") || path.startsWith("/v1/competition/instagram/")
      ? 55_000
      : 15_000
  log("info", "kiara_api.request_started", { upstream_host: target.host, timeout_ms: timeoutMs })
  try {
    const response = await fetch(target, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
        "X-Correlation-ID": requestId,
        ...(bypass ? { "x-vercel-protection-bypass": bypass } : {}),
        ...init.headers,
      },
    })
    if (options.stream && response.ok && (response.headers.get("content-type") ?? "").includes("text/event-stream")) {
      log("info", "kiara_api.stream_started", { upstream_status: response.status })
      return new Response(response.body, { status: 200, headers: {
        "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store", "X-Accel-Buffering": "no",
        "X-Correlation-ID": response.headers.get("x-correlation-id") || requestId,
      } })
    }
    if (options.video && response.ok && (response.headers.get("content-type") ?? "").startsWith("video/mp4")) {
      log("info", "kiara_api.request_completed", { upstream_status: response.status })
      const headers = new Headers({ "Content-Type": "video/mp4", "Cache-Control": "no-store, private", "X-Correlation-ID": response.headers.get("x-correlation-id") || requestId })
      for (const name of ["x-kiara-part", "x-kiara-parts"]) {
        const value = response.headers.get(name)
        if (value && /^\d{1,2}$/.test(value)) headers.set(name, value)
      }
      return new Response(response.body, { status: 200, headers })
    }
    if (response.status === 204 || response.status === 205) {
      log("info", "kiara_api.request_completed", { upstream_status: response.status })
      return new Response(null, { status: response.status, headers: { "Cache-Control": "no-store", "X-Correlation-ID": response.headers.get("x-correlation-id") || requestId } })
    }
    const text = await response.text()
    const contentType = response.headers.get("content-type") ?? ""
    let payload: unknown
    try {
      payload = JSON.parse(text)
    } catch {
      log("error", "kiara_api.invalid_response", { upstream_status: response.status, content_type: contentType })
      return upstreamFormatError(response.status, contentType, requestId)
    }
    const level = response.ok ? "info" : response.status < 500 ? "warn" : "error"
    log(level, response.ok ? "kiara_api.request_completed" : "kiara_api.upstream_response", { upstream_status: response.status })
    const headers = new Headers({ "Cache-Control": "no-store", "X-Correlation-ID": response.headers.get("x-correlation-id") || requestId })
    const retryAfter = response.headers.get("retry-after")
    if (retryAfter) headers.set("Retry-After", retryAfter)
    return Response.json(payload, { status: response.status, headers })
  } catch (error) {
    const timedOut = error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")
    const cause = error instanceof Error ? error.message : String(error)
    log("error", timedOut ? "kiara_api.timeout" : "kiara_api.connection_failed", { error_class: error instanceof Error ? error.name : "UnknownError" })
    return timedOut
      ? errorResponse(504, "api_timeout", "A API ultrapassou " + Math.round(timeoutMs / 1000) + " segundos. A pesquisa pode continuar no backend; use Atualizar resultados antes de repeti-la.", requestId)
      : errorResponse(502, "api_connection_failed", "O site não conseguiu se conectar ao backend. Verifique KIARA_API_URL, o domínio e o estado do serviço.", requestId, { reason: cause.slice(0, 160) })
  }
}
