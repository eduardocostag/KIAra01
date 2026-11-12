import { WhatsAppWebWorkspace } from "@/components/app-shell/whatsapp-web-workspace"
import { WhatsAppGatewayWorkspace } from "@/components/app-shell/whatsapp-gateway-workspace"
import { AppShell } from "@/components/app-shell/app-shell"
import { InboxHub } from "@/components/app-shell/inbox-hub"
import { LeadsOverview } from "@/components/app-shell/leads-overview"
import { notFound } from "next/navigation"
import { ChatWorkspace } from "@/components/chat/chat-workspace"
import { HunterClient } from "@/app/(app)/app/(leads-module)/hunter/hunter-client"
import { previewEntries } from "./leads-fixtures"

export default async function Page({ searchParams }: { searchParams: Promise<{ workspace?: string; view?: string }> }) {
  if (process.env.NODE_ENV !== "development") notFound()
  const { workspace, view } = await searchParams
  const content = workspace === "chat" ? <ChatWorkspace />
    : workspace === "gateway" ? <WhatsAppGatewayWorkspace />
      : workspace === "hunter" ? <HunterClient />
        : workspace === "contacts" ? <InboxHub entries={previewEntries} prospectError="" initialView={view ?? "contacts"} initialContactId="" />
          : workspace === "leads-home" ? <LeadsOverview entries={previewEntries} available now={new Date().getTime()} />
          : <WhatsAppWebWorkspace entries={[]} />
  return <AppShell>{content}</AppShell>
}
