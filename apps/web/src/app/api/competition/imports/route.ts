import { kiaraApi } from "@/lib/api/server-client"
import { adminGuardResponse } from "@/lib/competition/admin-route"

export async function POST(request: Request) {
  const guard = await adminGuardResponse()
  if (guard) return guard
  return kiaraApi("/v1/competition/imports", { method: "POST", body: await request.text() })
}
