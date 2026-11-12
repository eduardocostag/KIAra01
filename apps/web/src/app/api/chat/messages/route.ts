import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 120

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const text = await request.text()
  if (text.length > 200000) return Response.json({ error: { message: "Histórico grande demais." } }, { status: 413 })
  let body: unknown
  try { body = JSON.parse(text) }
  catch { return Response.json({ error: { message: "Mensagem inválida." } }, { status: 400 }) }
  return kiaraApi("/v1/chat/messages", { method: "POST", body: JSON.stringify(body) })
}
