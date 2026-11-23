import { kiaraApi } from "@/lib/api/server-client"

export const maxDuration = 100

export async function POST(request: Request) {
  let body: unknown
  try { body = await request.json() } catch { return Response.json({ error: { message: "Dados inválidos." } }, { status: 400 }) }
  return kiaraApi("/v1/sdr/simulate", { method: "POST", body: JSON.stringify(body) })
}
