import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 60

const actions = new Set(["status", "connect", "sync"])

/** WhatsApp on the Debian server (OpenWA through the Kiara gateway): status, QR connection and inbox sync. */
export async function POST(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const { action } = await params
  if (!actions.has(action)) return Response.json({ error: { message: "Ação desconhecida." } }, { status: 404 })
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  return kiaraApi(`/v1/whatsapp-server/${action}`, { method: action === "status" ? "GET" : "POST" })
}
