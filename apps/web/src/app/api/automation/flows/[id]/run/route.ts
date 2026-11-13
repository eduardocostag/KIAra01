import { kiaraApi } from "@/lib/api/server-client"

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return kiaraApi(`/v1/automation/flows/${encodeURIComponent(id)}/run`, { method: "POST" })
}
