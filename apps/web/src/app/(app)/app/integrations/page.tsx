import { BarChart3, CheckCircle2, DatabaseZap, Gauge, MessageCircle as Instagram, ShieldCheck, Sparkles } from "lucide-react"
import { PageHeader } from "@/components/app-shell/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { IntegrationSettings } from "@/components/app-shell/integration-settings"

const googleCapabilities = [
  { icon: Gauge, label: "Google Ads", detail: "Conexão e leitura de campanhas" },
  { icon: BarChart3, label: "Diagnóstico", detail: "Performance, conversões e oportunidades" },
  { icon: DatabaseZap, label: "Data Manager", detail: "Eventos e audiências com consentimento" },
  { icon: Sparkles, label: "Analytics", detail: "Relatórios e configuração do GA4" },
]

export default function IntegrationsPage() {
  return <div className="space-y-6">
    <PageHeader eyebrow="Conectividade" title="Integrações" description="Conecte provedores oficiais, acompanhe permissões e valide a saúde sem expor credenciais." />
    <div className="grid gap-5 xl:grid-cols-2">
      <Card className="border-primary/25">
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div className="flex gap-3"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-fuchsia-500 to-orange-400 text-white"><Instagram aria-hidden="true" /></span><div><CardTitle>Instagram Messaging</CardTitle><p className="mt-1 text-xs text-muted-foreground">Meta · conta profissional</p></div></div>
          <Badge variant="outline">Não conectado</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-xl bg-muted/50 p-4 text-sm"><p className="flex items-center gap-2 font-medium"><CheckCircle2 aria-hidden="true" className="size-4 text-amber-600" />Configuração necessária</p><p className="mt-2 text-xs leading-5 text-muted-foreground">OAuth, webhook e permissões do aplicativo Meta ainda precisam ser configurados.</p></div>
          <div><Button disabled aria-describedby="instagram-setup-note">Conectar Instagram</Button><p id="instagram-setup-note" className="mt-2 text-xs text-muted-foreground">O botão será liberado quando as credenciais Meta estiverem cadastradas no servidor.</p></div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-sky-500/30 bg-gradient-to-br from-card via-card to-sky-500/5">
        <CardHeader className="flex-row items-start justify-between gap-4">
          <div className="flex gap-3"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-blue-500 via-red-500 to-yellow-400 text-white shadow-lg shadow-blue-500/15"><BarChart3 aria-hidden="true" /></span><div><CardTitle>Google Growth</CardTitle><p className="mt-1 text-xs text-muted-foreground">Google Ads · Data Manager · Analytics</p></div></div>
          <Badge className="bg-sky-500/10 text-sky-700 hover:bg-sky-500/10 dark:text-sky-300" variant="secondary">Base incorporada</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-2">{googleCapabilities.map(({ icon: Icon, label, detail }) => <div key={label} className="rounded-xl border bg-background/70 p-3"><p className="flex items-center gap-2 text-sm font-medium"><Icon aria-hidden="true" className="size-4 text-primary" />{label}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p></div>)}</div>
          <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 text-xs leading-5 text-muted-foreground">A integração operacional ainda requer OAuth e contas Google dos clientes. Nesta fase, nenhuma campanha, verba ou audiência é alterada.</div>
          <Button disabled aria-describedby="google-growth-note">Conectar conta Google</Button>
          <p id="google-growth-note" className="text-xs text-muted-foreground">Será liberado na fase de conexão OAuth e diagnóstico somente leitura.</p>
        </CardContent>
      </Card>
    </div>
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck aria-hidden="true" className="size-4 text-primary" />Política de conexão e automação</CardTitle></CardHeader><CardContent className="grid gap-4 text-sm text-muted-foreground md:grid-cols-3"><p>O primeiro acesso é somente leitura para validar conta, campanhas, métricas e atribuição.</p><p>Tokens ficam no servidor e a interface mostra apenas o estado da conexão e os escopos concedidos.</p><p>Publicação, mudança de verba ou segmentação exigirá preview, limite de gasto e aprovação explícita.</p></CardContent></Card>
    <IntegrationSettings />
  </div>
}
