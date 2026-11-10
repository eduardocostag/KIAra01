import { kiaraApi } from "@/lib/api/server-client"
export async function PATCH(request: Request, { params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Configuração inválida." } }, { status: 400 }) }
  return kiaraApi(`/v1/inbox/threads/${encodeURIComponent(threadId)}/automation`, { method: "PATCH", body: JSON.stringify(body) })
}
