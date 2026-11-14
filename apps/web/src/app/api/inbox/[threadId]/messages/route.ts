import { kiaraApi } from "@/lib/api/server-client"

// A WhatsApp reply is sent like a person types it (spacing + "typing…"), which can take ~25 s.
export const maxDuration = 60

export async function POST(request: Request, { params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Mensagem inválida." } }, { status: 400 }) }
  return kiaraApi(`/v1/inbox/threads/${encodeURIComponent(threadId)}/messages`, { method: "POST", body: JSON.stringify(body) })
}
