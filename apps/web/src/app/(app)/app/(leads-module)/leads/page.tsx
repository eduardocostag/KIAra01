import { LeadsOverview } from "@/components/app-shell/leads-overview"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function DashboardPage() {
  const pipeline = await getPipelineDTO()
    .then((entries) => ({ entries, available: true }))
    .catch(() => ({ entries: [], available: false }))
  return <LeadsOverview entries={pipeline.entries} available={pipeline.available} now={new Date().getTime()} />
}
