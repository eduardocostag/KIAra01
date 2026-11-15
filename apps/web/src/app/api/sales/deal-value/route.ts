import { kiaraApi } from "@/lib/api/server-client"

export async function PUT(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 }) }
  return kiaraApi("/v1/sales/deal-value", { method: "PUT", body: JSON.stringify(body) })
}
