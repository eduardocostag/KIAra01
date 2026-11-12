import { AlertCircle } from "lucide-react"
import { notFound } from "next/navigation"

import { UnifiedInbox } from "@/components/app-shell/unified-inbox"
import { PageHeader } from "@/components/app-shell/page-header"
import { SupportSectionNav } from "@/components/app-shell/workspace-section-nav"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { getInboxDTO, KiaraApiError } from "@/lib/api/inbox"

type InboxConversationPageProps = {
  params: Promise<{ conversationId: string }>
  searchParams: Promise<{
    q?: string | string[]
    filter?: string | string[]
  }>
}

export default async function InboxConversationPage({
  params,
}: InboxConversationPageProps) {
  const { conversationId } = await params

  let inbox
  try {
    inbox = await getInboxDTO()
  } catch (error) {
    const correlationId =
      error instanceof KiaraApiError ? error.correlationId : crypto.randomUUID()

    return (
      <div className="space-y-6">
        <SupportSectionNav />
        <PageHeader
          eyebrow="Atendimento multicanal"
          title="Caixa de entrada"
          description="A conversa não pôde ser carregada."
        />
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Não foi possível consultar a API</AlertTitle>
          <AlertDescription>
            Tente novamente em instantes. Referência: {correlationId}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!inbox.conversations.some((conversation) => conversation.id === conversationId)) {
    notFound()
  }

  return (
    <div className="space-y-6">
      <SupportSectionNav />
      <PageHeader
        eyebrow="Atendimento multicanal"
        title="Caixa de entrada"
        description="Qualifique a conversa e prepare a próxima resposta com aprovação humana."
      />
      <UnifiedInbox conversations={inbox.conversations} initialId={conversationId} canSend={inbox.canSend} />
    </div>
  )
}
