import { WhatsAppWebWorkspace } from "@/components/app-shell/whatsapp-web-workspace"
import { WhatsAppInbox, WhatsAppSectionShell } from "@/components/app-shell/whatsapp-inbox"
import { AppShell } from "@/components/app-shell/app-shell"
import { InboxHub } from "@/components/app-shell/inbox-hub"
import { notFound } from "next/navigation"
import { ComingSoon } from "@/components/early-access/coming-soon"
import { LaunchBadge } from "@/components/early-access/launch-badge"
import { ChatWorkspace } from "@/components/chat/chat-workspace"
import { AutomationWorkspace } from "@/components/automation/automation-workspace"
import { HunterClient } from "@/app/(app)/app/(leads-module)/hunter/hunter-client"
import { previewConversations, previewEntries } from "./leads-fixtures"

export default async function Page({ searchParams }: { searchParams: Promise<{ workspace?: string; view?: string }> }) {
  if (process.env.NODE_ENV !== "development") notFound()
  const { workspace, view } = await searchParams
  // Conversation modules own their full-height shell, like in the real routes.
  if (workspace === "chat") return <ChatWorkspace />
  if (workspace === "automation-flow") return <AutomationWorkspace />
  if (workspace === "launch-badge") return <div className="grid min-h-dvh place-items-center bg-[#07060d] p-8"><div className="flex w-64 flex-col items-center rounded-3xl border border-white/10 bg-black/40 p-8 text-center"><h2 className="mb-2 text-xl font-semibold">KIARA Chat</h2><p className="mb-8 text-sm text-muted-foreground">Conversa, voz e criação com IA.</p><LaunchBadge /><span className="text-sm">Ver novidade</span></div></div>
  if (workspace === "soon-whatsapp" || workspace === "soon-chat" || workspace === "soon-automation") return <ComingSoon module={workspace.slice(5) as "whatsapp" | "chat" | "automation"} />
  if (workspace === "whatsapp") return <WhatsAppInbox conversations={view === "empty" ? [] : previewConversations} canSend />
  if (workspace === "automation") return <WhatsAppSectionShell title="Automação"><WhatsAppWebWorkspace entries={previewEntries} /></WhatsAppSectionShell>
  const content = workspace === "hunter" ? <HunterClient />
    : workspace === "contacts" ? <InboxHub entries={previewEntries} prospectError="" initialView={view ?? "contacts"} initialContactId="" />
      : <WhatsAppWebWorkspace entries={[]} />
  return <AppShell previewModule={workspace === "hunter" || workspace === "contacts" ? "/app/leads" : undefined}>{content}</AppShell>
}
