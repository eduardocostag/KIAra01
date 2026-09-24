import { kiaraApi } from "@/lib/api/server-client"
import { adminGuardResponse } from "@/lib/competition/admin-route"

export async function GET() {
  const guard = await adminGuardResponse()
  if (guard) return guard
  return kiaraApi("/v1/competition/tools")
}
