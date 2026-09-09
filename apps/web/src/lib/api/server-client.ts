import "server-only"
import { auth } from "@clerk/nextjs/server"

export async function kiaraApi(path: string, init: RequestInit = {}) {
  const { getToken } = await auth()
  const token = await getToken()
  if (!token) return Response.json({ error: { message: "Sessão inválida." } }, { status: 401 })
  const base = process.env.KIARA_API_URL?.replace(/\/$/, "")
  if (!base) return Response.json({ error: { message: "API não configurada." } }, { status: 503 })
  const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET?.trim()
  const correlationId = crypto.randomUUID()
  try {
    const response = await fetch(`${base}${path}`, { ...init, cache: "no-store", signal: AbortSignal.timeout(path.endsWith("/confirm") ? 190_000 : 15_000), headers: {
    "Content-Type": "application/json", Authorization: `Bearer ${token}`,
    "X-Correlation-ID": correlationId,
    ...(bypass ? { "x-vercel-protection-bypass": bypass } : {}), ...init.headers,
    } })
    const text = await response.text()
    let payload: unknown
    try { payload = JSON.parse(text) } catch {
      return Response.json({ error: { message: "A API não retornou dados válidos. Atualize os resultados para consultar a pesquisa salva.", request_id: correlationId } }, { status: 502 })
    }
    return Response.json(payload, { status: response.status, headers: { "Cache-Control": "no-store", "X-Correlation-ID": correlationId } })
  } catch {
    return Response.json({ error: { message: "A API não respondeu a tempo. A pesquisa pode continuar em execução; atualize os resultados antes de repetir.", request_id: correlationId } }, { status: 504 })
  }
}
