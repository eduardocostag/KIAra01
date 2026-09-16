import { PipelineBoard } from "@/components/app-shell/pipeline-board"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function PipelinePage() {
  const entries = await getPipelineDTO().catch(() => [])
  return <PipelineBoard initialEntries={entries} />
}
