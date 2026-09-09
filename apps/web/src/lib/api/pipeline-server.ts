import "server-only"
import { requireWorkspace } from "@/lib/auth"
import { kiaraApi } from "./server-client"
import { parsePipeline } from "./pipeline"

export async function getPipelineDTO() {
  await requireWorkspace()
  const response = await kiaraApi("/v1/pipeline")
  const payload = await response.json()
  if (!response.ok) throw new Error(payload?.error?.message || "Não foi possível consultar o Pipeline.")
  return parsePipeline(payload)
}
