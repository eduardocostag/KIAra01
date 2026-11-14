import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 60

/** Official WhatsApp (Meta Cloud API): status, Embedded Signup completion and disconnect. */
export async function POST(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const { action } = await params
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  if (action === "status") return kiaraApi("/v1/whatsapp-official/status")
  if (action === "disconnect") return kiaraApi("/v1/whatsapp-official", { method: "DELETE" })
  if (action === "connect") {
    const body = await request.text()
    if (body.length > 4000) return Response.json({ error: { message: "Dados de conexão inválidos." } }, { status: 413 })
    return kiaraApi("/v1/whatsapp-official/connect", { method: "POST", body })
  }
  return Response.json({ error: { message: "Ação desconhecida." } }, { status: 404 })
}
