import { UnifiedInbox } from "@/components/app-shell/unified-inbox"
import { PageHeader } from "@/components/app-shell/page-header"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { SupportSectionNav } from "@/components/app-shell/workspace-section-nav"
import { getInboxDTO } from "@/lib/api/inbox"
export default async function InboxPage() {
  const inbox = await getInboxDTO().then(data => ({ ...data, error: "" })).catch(() => ({ conversations: [], canSend: false, error: "Não foi possível sincronizar a caixa de entrada. Atualize para tentar novamente." }))
  return <div className="space-y-4"><SupportSectionNav /><PageHeader compact mobileMinimal eyebrow="Atendimento" title="Caixa de entrada" description="WhatsApp, Instagram e outros canais conectados em um só lugar." actions={<RefreshWorkspace />} />{inbox.error && <p role="alert" className="rounded-xl border border-destructive/30 p-4 text-sm text-destructive">{inbox.error}</p>}<UnifiedInbox conversations={inbox.conversations} canSend={inbox.canSend} /></div>
}
