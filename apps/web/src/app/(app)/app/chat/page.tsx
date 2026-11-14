import { ChatWorkspace } from "@/components/chat/chat-workspace"
import { requireWorkspace } from "@/lib/auth"

export const metadata = { title: "KIARA Chat" }

export default async function KiaraChatPage() {
  const { userId, isSystemAdmin } = await requireWorkspace()
  return <ChatWorkspace userId={userId} isAdmin={isSystemAdmin} />
}
