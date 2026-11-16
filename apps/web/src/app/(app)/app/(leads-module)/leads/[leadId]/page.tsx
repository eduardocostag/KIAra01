import { notFound } from "next/navigation"
import { LeadDetail } from "@/components/app-shell/lead-detail"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function LeadPage({ params }: { params: Promise<{ leadId: string }> }) {
  const { leadId } = await params
  const result = await getPipelineDTO().then((entries) => ({ entries, error: false })).catch(() => ({ entries: [], error: true }))
  if (result.error) return <div className="kiara-soft-panel p-8"><h1 className="text-2xl font-semibold">Contato indisponível</h1><p className="mt-3 text-muted-foreground">Não foi possível consultar os leads agora. Seus dados não foram apagados.</p><div className="mt-5"><RefreshWorkspace /></div></div>
  const entry = result.entries.find((item) => item.consumer.id === leadId)
  if (!entry) notFound()
  return <LeadDetail entry={entry} />
}
