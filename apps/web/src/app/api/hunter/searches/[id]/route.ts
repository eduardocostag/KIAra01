import { kiaraApi } from "@/lib/api/server-client"

export async function GET(_: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  return kiaraApi(`/v1/hunter/searches/${encodeURIComponent(id)}`)
}
