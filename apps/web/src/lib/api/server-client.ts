import "server-only"
import { auth } from "@clerk/nextjs/server"

export async function kiaraApi(path: string, init: RequestInit = {}) {
  const { getToken } = await auth()
  const token = await getToken()
  if (!token) return Response.json({ error: { message: "Sessão inválida." } }, { status: 401 })
  const base = process.env.KIARA_API_URL?.replace(/\/$/, "")
  if (!base) return Response.json({ error: { message: "API não configurada." } }, { status: 503 })
  const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET?.trim()
  return fetch(`${base}${path}`, { ...init, cache: "no-store", headers: {
    "Content-Type": "application/json", Authorization: `Bearer ${token}`,
    "X-Correlation-ID": crypto.randomUUID(),
    ...(bypass ? { "x-vercel-protection-bypass": bypass } : {}), ...init.headers,
  } })
}
