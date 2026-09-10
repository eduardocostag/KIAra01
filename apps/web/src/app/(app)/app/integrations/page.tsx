import { ShieldCheck } from "lucide-react"
import { IntegrationSettings } from "@/components/app-shell/integration-settings"
import { PageHeader } from "@/components/app-shell/page-header"

export default function IntegrationsPage() {
  return <div className="mx-auto max-w-6xl space-y-7"><PageHeader eyebrow="Connection hub" title="Conecte a Kiara ao seu crescimento." description="Ative somente os canais necessários. Cada conexão usa credenciais oficiais, isoladas e criptografadas por workspace." /><IntegrationSettings /><div className="flex items-start gap-3 rounded-2xl bg-emerald-500/8 p-4 text-xs leading-5 text-muted-foreground"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" /><p><span className="font-medium text-foreground">Você mantém o controle.</span> Nenhuma publicação, alteração de verba ou mensagem acontece apenas por salvar credenciais.</p></div></div>
}
