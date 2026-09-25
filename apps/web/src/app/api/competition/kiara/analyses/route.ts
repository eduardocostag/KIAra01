import { kiaraApi } from "@/lib/api/server-client"
import { adminGuardResponse } from "@/lib/competition/admin-route"

export const maxDuration = 60

export async function POST(request: Request) {
  const guard = await adminGuardResponse()
  if (guard) return guard
  return kiaraApi("/v1/competition/kiara/analyses", { method: "POST", body: await request.text() })
}
