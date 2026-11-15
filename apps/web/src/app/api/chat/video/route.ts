import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 120

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const text = await request.text()
  if (text.length > 10000) return Response.json({ error: { message: "Pedido grande demais." } }, { status: 413 })
  let body: { action?: unknown; prompt?: unknown; job_id?: unknown }
  try { body = JSON.parse(text) }
  catch { return Response.json({ error: { message: "Pedido inválido." } }, { status: 400 }) }
  const action = body.action === "status" || body.action === "download" ? body.action : "start"
  const payload = action === "start"
    ? { action, prompt: typeof body.prompt === "string" ? body.prompt.trim().slice(0, 3000) : "" }
    : { action, job_id: typeof body.job_id === "string" && /^[0-9a-f]{32}$/.test(body.job_id) ? body.job_id : "" }
  return kiaraApi("/v1/chat/video", { method: "POST", body: JSON.stringify(payload) })
}
