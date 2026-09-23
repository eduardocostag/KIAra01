import { InboxHub } from "@/components/app-shell/inbox-hub"
import { PageHeader } from "@/components/app-shell/page-header"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function InboxPage({ searchParams }: { searchParams: Promise<{ view?: string; contact?: string }> }) {
  const [params, pipeline] = await Promise.all([
    searchParams,
    getPipelineDTO().then((entries) => ({ entries, error: "" })).catch(() => ({ entries: [], error: "Não foi possível carregar os contatos prospectados. Use Atualizar para tentar novamente." })),
  ])
  const initialView = params.view ?? "contacts"
  return <div className="space-y-4"><PageHeader compact eyebrow="Relacionamento" title="Leads" description="Encontre, organize e acompanhe todos os seus contatos em um só lugar." actions={<RefreshWorkspace />} /><InboxHub entries={pipeline.entries} prospectError={pipeline.error} initialView={initialView} initialContactId={params.contact ?? ""} /></div>
}
