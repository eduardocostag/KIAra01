import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 300

// The chat answer while it is written (server-sent events). Photos and PDFs may make the body up to ~4.4 MB.
export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const text = await request.text()
  if (text.length > 4_600_000) return Response.json({ error: { message: "Anexos grandes demais (máximo de 3 MB no total)." } }, { status: 413 })
  try { JSON.parse(text) }
  catch { return Response.json({ error: { message: "Mensagem inválida." } }, { status: 400 }) }
  return kiaraApi("/v1/chat/stream", { method: "POST", body: text }, { stream: true })
}
