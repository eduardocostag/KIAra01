import { redirect } from "next/navigation"
import { ChatWorkspace } from "@/components/chat/chat-workspace"
import { requireWorkspace } from "@/lib/auth"

export const metadata = { title: "KIARA Chat" }

export default async function KiaraChatPage() {
  const { userId, isSystemAdmin, modules } = await requireWorkspace()
  if (!modules.includes("chat")) redirect("/app")  // the proxy redirects first; this is the backstop
  return <ChatWorkspace userId={userId} isAdmin={isSystemAdmin} />
}
