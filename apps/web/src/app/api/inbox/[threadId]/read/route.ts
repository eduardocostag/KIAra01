import { kiaraApi } from "@/lib/api/server-client"
export async function POST(_request: Request, { params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params
  return kiaraApi(`/v1/inbox/threads/${encodeURIComponent(threadId)}/read`, { method: "POST", body: "{}" })
}
