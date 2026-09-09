import { PageHeader } from "@/components/app-shell/page-header"
import { PipelineWorkspace } from "@/components/app-shell/pipeline-workspace"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function PipelinePage() {
  const result = await getPipelineDTO().then((entries) => ({ entries, error: "" })).catch((error: unknown) => ({ entries: [], error: error instanceof Error ? error.message : "Pipeline indisponível." }))
  return <div className="space-y-6"><PageHeader eyebrow="CRM · jornada comercial" title="Pipeline" description="Da descoberta ao negócio fechado. Acompanhe os leads do Hunter e atualize cada etapa da sua operação." /><PipelineWorkspace initialEntries={result.entries} initialError={result.error} /></div>
}
