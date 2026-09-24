import { kiaraApi } from "@/lib/api/server-client"
import { adminGuardResponse } from "@/lib/competition/admin-route"

export async function GET(_: Request, { params }: { params: Promise<{ analysisId: string }> }) {
  const guard = await adminGuardResponse()
  if (guard) return guard
  const { analysisId } = await params
  return kiaraApi(`/v1/competition/analyses/${encodeURIComponent(analysisId)}`)
}
