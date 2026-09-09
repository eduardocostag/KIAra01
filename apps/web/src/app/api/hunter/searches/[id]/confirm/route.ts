import { kiaraApi } from "@/lib/api/server-client"
export const maxDuration = 240
export async function POST(_: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  return kiaraApi(`/v1/hunter/searches/${encodeURIComponent(id)}/confirm`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } })
}
