import { AlertCircle } from "lucide-react"

import { InboxWorkspace } from "@/components/app-shell/inbox-workspace"
import { PageHeader } from "@/components/app-shell/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { getInboxDTO, KiaraApiError } from "@/lib/api/inbox"

async function loadInbox() {
  try {
    return { inbox: await getInboxDTO(), correlationId: null }
  } catch (error) {
    return {
      inbox: null,
      correlationId: error instanceof KiaraApiError ? error.correlationId : crypto.randomUUID(),
    }
  }
}

export default async function InboxPage() {
  const { inbox, correlationId } = await loadInbox()
  if (inbox) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Canal oficial"
          title="Inbox do Instagram"
          description="Qualifique conversas inbound, prepare rascunhos e mantenha aprovação e envio como etapas separadas."
        />
        <InboxWorkspace initialConversations={inbox.conversations} />
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Canal oficial" title="Inbox do Instagram" description="A Inbox real não pôde ser carregada." />
      <Alert variant="destructive">
        <AlertCircle />
        <AlertTitle>Não foi possível consultar a API</AlertTitle>
        <AlertDescription>Tente novamente em instantes. Referência: {correlationId}</AlertDescription>
      </Alert>
    </div>
  )
}
