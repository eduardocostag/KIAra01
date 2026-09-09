import { CopilotIntro } from "@/components/app-shell/copilot-intro"
import { PageHeader } from "@/components/app-shell/page-header"
import { SettingsForm } from "@/components/app-shell/settings-form"

export default function SettingsPage() {
  return <div className="space-y-6"><PageHeader eyebrow="Workspace" title="Configurações comerciais" description="Defina identidade, oferta, mensagens e cadência usadas em todo o ciclo de prospecção." /><CopilotIntro title="Uma voz consistente em toda abordagem." description="Configure sua identidade uma vez; eu aplico o contexto aos modelos, lembretes e próximos movimentos." /><SettingsForm /></div>
}
