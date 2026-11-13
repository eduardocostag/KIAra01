import { kiaraApi } from "@/lib/api/server-client"

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 }) }
  return kiaraApi(`/v1/approvals/${encodeURIComponent(id)}/decision`, { method: "POST", body: JSON.stringify(body) })
}
