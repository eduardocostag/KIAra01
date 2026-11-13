import { kiaraApi } from "@/lib/api/server-client"

type Params = { params: Promise<{ id: string }> }

export async function POST(request: Request, { params }: Params) {
  const { id } = await params
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 }) }
  return kiaraApi(`/v1/leads/${encodeURIComponent(id)}/company`, { method: "POST", body: JSON.stringify(body) })
}

export async function DELETE(_request: Request, { params }: Params) {
  const { id } = await params
  return kiaraApi(`/v1/leads/${encodeURIComponent(id)}/company`, { method: "DELETE" })
}
