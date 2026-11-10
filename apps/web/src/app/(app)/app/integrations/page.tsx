import { IntegrationSettings } from "@/components/app-shell/integration-settings"
import { PageHeader } from "@/components/app-shell/page-header"

export default function IntegrationsPage() {
  return <div className="mx-auto max-w-6xl space-y-6"><PageHeader title="Integrações" description="Conecte os canais e serviços da sua operação." /><IntegrationSettings /><details className="rounded-xl border p-4 text-xs text-muted-foreground"><summary className="cursor-pointer font-medium text-foreground">Sobre as conexões</summary><p className="mt-3 max-w-2xl leading-5">As credenciais ficam criptografadas e isoladas por workspace. Salvar uma conexão não inicia publicações, mensagens ou alterações de verba.</p></details></div>
}
