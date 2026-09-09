import { CheckCircle2, KeyRound, ShieldCheck } from "lucide-react"

import { IntegrationSettings } from "@/components/app-shell/integration-settings"
import { PageHeader } from "@/components/app-shell/page-header"
import { CopilotIntro } from "@/components/app-shell/copilot-intro"

const steps = [
  { icon: KeyRound, number: "01", title: "Gere suas credenciais", description: "Use os atalhos oficiais do Google ou da Meta." },
  { icon: ShieldCheck, number: "02", title: "Configure com segurança", description: "Os segredos são criptografados e separados por empresa." },
  { icon: CheckCircle2, number: "03", title: "Ative a sincronização", description: "A Kiara valida a conta antes de iniciar qualquer operação." },
]

export default function IntegrationsPage() {
  return <div className="mx-auto max-w-6xl space-y-6">
    <PageHeader eyebrow="Central de conexões" title="Integrações" description="Conecte os canais da sua operação em um ambiente protegido e acompanhe o estado de cada conta." />

    <section aria-label="Como conectar" className="grid gap-px overflow-hidden rounded-2xl border bg-border md:grid-cols-3">
      {steps.map(({ icon: Icon, number, title, description }) => <div key={number} className="flex gap-4 bg-card p-5">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="size-4" aria-hidden="true" /></span>
        <div><p className="text-[10px] font-semibold tracking-[.16em] text-muted-foreground">PASSO {number}</p><h2 className="mt-1 text-sm font-semibold">{title}</h2><p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p></div>
      </div>)}
    </section>

    <CopilotIntro title="Conecte somente o que você precisa agora." description="Eu verifico cada integração e mantenho credenciais, status e próximos passos no mesmo lugar." />
    <IntegrationSettings />

    <div className="flex items-start gap-3 rounded-2xl border bg-muted/30 p-4 text-xs leading-5 text-muted-foreground">
      <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
      <p><span className="font-medium text-foreground">Você mantém o controle.</span> A primeira conexão é somente leitura. Publicação, alteração de verba, segmentação ou envio de mensagens exigirá confirmação explícita.</p>
    </div>
  </div>
}
