import { kiaraApi } from "@/lib/api/server-client"

export async function POST(
  _: Request,
  context: { params: Promise<{ id: string; resultId: string }> },
) {
  const { id, resultId } = await context.params
  return kiaraApi(
    `/v1/hunter/searches/${encodeURIComponent(id)}/results/${encodeURIComponent(resultId)}/add-lead`,
    { method: "POST" },
  )
}
