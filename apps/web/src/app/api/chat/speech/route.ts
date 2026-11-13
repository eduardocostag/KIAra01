import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 60

/** Kiara's neural voice (Francisca) for the cloud chat; the API checks the user and the text size. */
export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: { message: "Origem não autorizada." } }, { status: 403 })
  }
  const text = await request.text()
  if (text.length > 20000) return Response.json({ error: { message: "Texto grande demais para falar." } }, { status: 413 })
  return kiaraApi("/v1/chat/speech", { method: "POST", body: text })
}
