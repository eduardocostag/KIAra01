import { LeadsDashboard } from "@/components/app-shell/leads-dashboard"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function DashboardPage() {
  const pipeline = await getPipelineDTO()
    .then((entries) => ({ entries, available: true }))
    .catch(() => ({ entries: [], available: false }))
  return <LeadsDashboard pipeline={pipeline} />
}
