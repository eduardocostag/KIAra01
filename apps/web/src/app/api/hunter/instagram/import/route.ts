import { kiaraApi } from "@/lib/api/server-client"

export async function POST(request: Request) {
  return kiaraApi("/v1/hunter/instagram/import", { method: "POST", body: await request.text() })
}
