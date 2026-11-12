import { kiaraApi } from "@/lib/api/server-client"

export async function GET() {
  return kiaraApi("/v1/chat/status")
}
