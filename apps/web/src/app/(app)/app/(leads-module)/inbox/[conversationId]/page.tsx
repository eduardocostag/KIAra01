import { redirect } from "next/navigation"

export default async function InboxConversationPage({ params }: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await params
  redirect(`/app/whatsapp?c=${encodeURIComponent(conversationId)}`)
}
