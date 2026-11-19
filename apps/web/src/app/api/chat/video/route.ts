import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 300

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const text = await request.text()
  if (text.length > 10000) return Response.json({ error: { message: "Pedido grande demais." } }, { status: 413 })
  let body: { action?: unknown; prompt?: unknown; job_id?: unknown; part?: unknown; raw?: unknown }
  try { body = JSON.parse(text) }
  catch { return Response.json({ error: { message: "Pedido inválido." } }, { status: 400 }) }
  const action = body.action === "status" || body.action === "download" ? body.action : "start"
  const jobId = typeof body.job_id === "string" && /^[0-9a-f]{32}$/.test(body.job_id) ? body.job_id : ""
  // Narrated videos are downloaded in parts (each part fits the hosting's response limit).
  const part = typeof body.part === "number" && Number.isInteger(body.part) && body.part >= 0 && body.part < 40 ? body.part : undefined
  // `raw`: the part comes back as plain MP4 bytes (no base64), lighter for phones.
  const raw = action === "download" && body.raw === true
  const payload = action === "start"
    ? { action, prompt: typeof body.prompt === "string" ? body.prompt.trim().slice(0, 3000) : "" }
    : { action, job_id: jobId, ...(action === "download" && part !== undefined ? { part } : {}), ...(raw ? { raw } : {}) }
  return kiaraApi("/v1/chat/video", { method: "POST", body: JSON.stringify(payload) }, { video: raw })
}
