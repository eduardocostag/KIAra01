import { CopilotIntro } from "@/components/app-shell/copilot-intro"
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
  const initialView = params.view ?? (!inbox.conversations.length && pipeline.entries.length ? "contacts" : "conversations")
  return <div className="space-y-6"><PageHeader eyebrow="Relacionamento" title="Inbox" description="Contatos prospectados e conversas reais, cada um no seu lugar." actions={<RefreshWorkspace />} /><CopilotIntro title="Vamos responder quem está mais perto de avançar." description="Sua fila separa contatos prospectados de conversas reais e mantém o contexto de cada pessoa." /><InboxHub conversations={inbox.conversations} entries={pipeline.entries} conversationError={inbox.error} prospectError={pipeline.error} initialView={initialView} /></div>
}
