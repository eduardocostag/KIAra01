import { WhatsAppInbox } from "@/components/app-shell/whatsapp-inbox"
import { getInboxDTO } from "@/lib/api/inbox"

export const metadata = { title: "WhatsApp" }

export default async function WhatsAppPage({ searchParams }: { searchParams: Promise<{ c?: string }> }) {
  const [{ c }, inbox] = await Promise.all([
    searchParams,
    getInboxDTO().then((data) => ({ ...data, error: "" })).catch(() => ({ conversations: [], canSend: false, error: "Não foi possível carregar as conversas. Atualize para tentar novamente." })),
  ])
  return <WhatsAppInbox conversations={inbox.conversations} canSend={inbox.canSend} initialId={c ?? ""} loadError={inbox.error} />
}
