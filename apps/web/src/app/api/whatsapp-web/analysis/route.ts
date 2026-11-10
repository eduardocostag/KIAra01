import { kiaraApi } from "@/lib/api/server-client"

export async function POST(request: Request) {
  let body: unknown
  try { body = await request.json() } catch {
    return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 })
  }
  return kiaraApi("/v1/whatsapp-web/analysis", { method: "POST", body: JSON.stringify(body) })
}
