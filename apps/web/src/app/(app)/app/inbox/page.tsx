import { InboxHub } from "@/components/app-shell/inbox-hub"
import { PageHeader } from "@/components/app-shell/page-header"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { getInboxDTO } from "@/lib/api/inbox"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export default async function InboxPage({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const [params, inbox, pipeline] = await Promise.all([
    searchParams,
    getInboxDTO().then((data) => ({ conversations: data.conversations, error: "" })).catch(() => ({ conversations: [], error: "Não foi possível carregar as conversas. Use Atualizar para tentar novamente." })),
    getPipelineDTO().then((entries) => ({ entries, error: "" })).catch(() => ({ entries: [], error: "Não foi possível carregar os contatos prospectados. Use Atualizar para tentar novamente." })),
  ])
  const initialView = params.view ?? "contacts"
  return <div className="space-y-4"><PageHeader compact eyebrow="Relacionamento" title="Leads" description="Encontre, organize e acompanhe todos os seus contatos em um só lugar." actions={<RefreshWorkspace />} /><InboxHub conversations={inbox.conversations} entries={pipeline.entries} conversationError={inbox.error} prospectError={pipeline.error} initialView={initialView} /></div>
}
