import { WhatsAppWebWorkspace } from "@/components/app-shell/whatsapp-web-workspace"
import { WhatsAppSectionShell } from "@/components/app-shell/whatsapp-inbox"
import { getPipelineDTO } from "@/lib/api/pipeline-server"

export const metadata = { title: "Automação do WhatsApp" }

export default async function WhatsAppAutomationPage() {
  const pipeline = await getPipelineDTO()
    .then((entries) => ({ entries, available: true }))
    .catch(() => ({ entries: [], available: false }))

  return <WhatsAppSectionShell title="Automação">
    <div className="space-y-4">
      {!pipeline.available && <p role="alert" className="rounded-xl border border-amber-400/25 bg-amber-400/5 p-4 text-sm text-amber-200">Não foi possível carregar os contatos do CRM. A configuração continua disponível; atualize a página para tentar novamente.</p>}
      <WhatsAppWebWorkspace entries={pipeline.entries} />
    </div>
  </WhatsAppSectionShell>
}
