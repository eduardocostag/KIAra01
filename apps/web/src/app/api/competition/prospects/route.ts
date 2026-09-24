import { kiaraApi } from "@/lib/api/server-client"
import { adminGuardResponse } from "@/lib/competition/admin-route"

export async function GET(request: Request) {
  const guard = await adminGuardResponse()
  if (guard) return guard
  const input = new URL(request.url)
  const query = new URLSearchParams()
  for (const key of ["analysis_id", "contactable_only", "limit"]) {
    const value = input.searchParams.get(key)
    if (value) query.set(key, value)
  }
  return kiaraApi(`/v1/competition/prospects?${query}`)
}
