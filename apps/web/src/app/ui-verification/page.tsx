import { WhatsAppWebWorkspace } from "@/components/app-shell/whatsapp-web-workspace"
import { WhatsAppInbox, WhatsAppSectionShell } from "@/components/app-shell/whatsapp-inbox"
import { AppShell } from "@/components/app-shell/app-shell"
import { InboxHub } from "@/components/app-shell/inbox-hub"
import { notFound } from "next/navigation"
import { ChatWorkspace } from "@/components/chat/chat-workspace"
import { HunterClient } from "@/app/(app)/app/(leads-module)/hunter/hunter-client"
import { previewConversations, previewEntries } from "./leads-fixtures"

export default async function Page({ searchParams }: { searchParams: Promise<{ workspace?: string; view?: string }> }) {
  if (process.env.NODE_ENV !== "development") notFound()
  const { workspace, view } = await searchParams
  // Conversation modules own their full-height shell, like in the real routes.
  if (workspace === "chat") return <ChatWorkspace />
  if (workspace === "whatsapp") return <WhatsAppInbox conversations={view === "empty" ? [] : previewConversations} canSend />
  if (workspace === "automation") return <WhatsAppSectionShell title="Automação"><WhatsAppWebWorkspace entries={previewEntries} /></WhatsAppSectionShell>
  const content = workspace === "hunter" ? <HunterClient />
    : workspace === "contacts" ? <InboxHub entries={previewEntries} prospectError="" initialView={view ?? "contacts"} initialContactId="" />
      : <WhatsAppWebWorkspace entries={[]} />
  return <AppShell>{content}</AppShell>
}
