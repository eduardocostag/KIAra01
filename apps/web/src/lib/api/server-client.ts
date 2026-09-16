import "server-only"
import { auth } from "@clerk/nextjs/server"

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
  if (status === 401 || status === 403) return errorResponse(502, "upstream_auth_rejected", "A API recusou a autenticação enviada pelo site. Verifique a configuração Clerk/OIDC do backend.", requestId, { upstream_status: status })
  if (status === 404) return errorResponse(502, "upstream_route_not_found", "A rota da API não foi encontrada. Verifique se KIARA_API_URL aponta para o backend correto.", requestId, { upstream_status: status })
  if (status === 412) return errorResponse(412, "version_conflict", "Este lead foi atualizado depois que a página foi carregada.", requestId, { upstream_status: status })
  if (status >= 500) return errorResponse(502, "upstream_server_error", "A API falhou internamente (HTTP " + status + ") e não devolveu o diagnóstico esperado.", requestId, { upstream_status: status })
  return errorResponse(502, "upstream_invalid_response", "A API respondeu em formato inválido (" + (contentType || "tipo não informado") + ", HTTP " + status + "). KIARA_API_URL pode estar apontando para uma página em vez do backend.", requestId, { upstream_status: status })
}

export async function kiaraApi(path: string, init: RequestInit = {}) {
  const requestId = crypto.randomUUID()
  const startedAt = Date.now()
  const method = init.method ?? "GET"
  const log = (level: "info" | "error", event: string, data: Record<string, unknown> = {}) => {
    const entry = { level, event, route: path, method, request_id: requestId, duration_ms: Date.now() - startedAt, ...data }
    if (level === "error") console.error(JSON.stringify(entry))
    else console.log(JSON.stringify(entry))
  }

  const { getToken } = await auth()
  const token = await getToken()
  if (!token) {
    log("error", "kiara_api.session_missing")
    return errorResponse(401, "session_missing", "Sua sessão não forneceu um token válido. Entre novamente na Kiara.", requestId)
  }

  const configuredBase = process.env.KIARA_API_URL?.trim()
  if (!configuredBase) {
    log("error", "kiara_api.not_configured")
    return errorResponse(503, "api_not_configured", "A conexão com o backend não está configurada. Cadastre KIARA_API_URL na Vercel.", requestId)
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
  const timeoutMs = path.endsWith("/confirm") ? 190_000 : 15_000
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
    const text = await response.text()
    const contentType = response.headers.get("content-type") ?? ""
    let payload: unknown
    try {
      payload = JSON.parse(text)
    } catch {
      log("error", "kiara_api.invalid_response", { upstream_status: response.status, content_type: contentType })
      return upstreamFormatError(response.status, contentType, requestId)
    }
    log(response.ok ? "info" : "error", response.ok ? "kiara_api.request_completed" : "kiara_api.upstream_error", { upstream_status: response.status })
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store", "X-Correlation-ID": response.headers.get("x-correlation-id") || requestId } })
  } catch (error) {
    const timedOut = error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")
    const cause = error instanceof Error ? error.message : String(error)
    log("error", timedOut ? "kiara_api.timeout" : "kiara_api.connection_failed", { error_class: error instanceof Error ? error.name : "UnknownError" })
    return timedOut
      ? errorResponse(504, "api_timeout", "A API ultrapassou " + Math.round(timeoutMs / 1000) + " segundos. A pesquisa pode continuar no backend; use Atualizar resultados antes de repeti-la.", requestId)
      : errorResponse(502, "api_connection_failed", "O site não conseguiu se conectar ao backend. Verifique KIARA_API_URL, o domínio e o estado do serviço.", requestId, { reason: cause.slice(0, 160) })
  }
}
