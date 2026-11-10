import { kiaraApi } from "@/lib/api/server-client"

export async function GET() { return kiaraApi("/v1/whatsapp-web/config") }

export async function PUT(request: Request) {
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 }) }
  return kiaraApi("/v1/whatsapp-web/config", { method: "PUT", body: JSON.stringify(body) })
}
