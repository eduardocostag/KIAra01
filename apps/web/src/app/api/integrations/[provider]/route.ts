import { kiaraApi } from "@/lib/api/server-client"

export async function PUT(request: Request, context: { params: Promise<{ provider: string }> }) {
  const { provider } = await context.params
  return kiaraApi(`/v1/integrations/${encodeURIComponent(provider)}`, { method: "PUT", body: await request.text() })
}
