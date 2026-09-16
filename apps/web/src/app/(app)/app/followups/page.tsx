import { FollowUpsWorkspace } from "@/components/app-shell/followups-workspace"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function FollowUpsPage() {
  const entries = await getPipelineDTO().catch(() => [])
  return <FollowUpsWorkspace entries={entries} />
}
