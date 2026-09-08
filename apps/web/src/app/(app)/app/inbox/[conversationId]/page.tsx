import { AlertCircle } from "lucide-react"
import { notFound } from "next/navigation"

import { InboxWorkspace } from "@/components/app-shell/inbox-workspace"
import { PageHeader } from "@/components/app-shell/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { getInboxDTO, KiaraApiError } from "@/lib/api/inbox"

type InboxConversationPageProps = {
  params: Promise<{ conversationId: string }>
  searchParams: Promise<{
    q?: string | string[]
    filter?: string | string[]
  }>
}

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? ""
}

export default async function InboxConversationPage({
  params,
  searchParams,
}: InboxConversationPageProps) {
  const [{ conversationId }, query] = await Promise.all([params, searchParams])

  let inbox
  try {
    inbox = await getInboxDTO()
  } catch (error) {
    const correlationId =
      error instanceof KiaraApiError ? error.correlationId : crypto.randomUUID()

    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Canal oficial"
          title="Inbox do Instagram"
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
      <PageHeader
        eyebrow="Canal oficial"
        title="Inbox do Instagram"
        description="Qualifique a conversa e prepare a próxima resposta com aprovação humana."
      />
      <InboxWorkspace
        initialConversations={inbox.conversations}
        source={inbox.source}
        initialConversationId={conversationId}
        initialQuery={first(query.q)}
        initialFilter={first(query.filter) || "Todas"}
      />
    </div>
  )
}
