import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 160

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const text = await request.text()
  if (text.length > 10000) return Response.json({ error: { message: "Descrição grande demais." } }, { status: 413 })
  let body: unknown
  try { body = JSON.parse(text) }
  catch { return Response.json({ error: { message: "Pedido inválido." } }, { status: 400 }) }
  const prompt = typeof (body as { prompt?: unknown })?.prompt === "string" ? (body as { prompt: string }).prompt.trim() : ""
  if (prompt.length < 3) return Response.json({ error: { message: "Descreva a imagem que você quer criar." } }, { status: 400 })
  return kiaraApi("/v1/chat/image", { method: "POST", body: JSON.stringify({ prompt: prompt.slice(0, 3000) }) })
}
