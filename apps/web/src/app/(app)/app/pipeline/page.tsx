import { InboxHub } from "@/components/app-shell/inbox-hub"
import { PageHeader } from "@/components/app-shell/page-header"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { getPipelineDTO } from "@/lib/api/pipeline-server"
export default async function PipelinePage({ searchParams }: { searchParams: Promise<{ view?: string; contact?: string }> }) {
  const [params, pipeline] = await Promise.all([searchParams, getPipelineDTO().then(entries => ({ entries, error: "" })).catch(() => ({ entries: [], error: "Não foi possível carregar os leads. Atualize para tentar novamente." }))])
  return <div className="space-y-4"><PageHeader compact mobileMinimal eyebrow="Operação comercial" title="Leads e CRM" description="Contatos, classificação, histórico e próxima ação." actions={<RefreshWorkspace />} /><InboxHub entries={pipeline.entries} prospectError={pipeline.error} initialView={params.view ?? "contacts"} initialContactId={params.contact ?? ""} /></div>
}
