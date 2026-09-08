import Link from "next/link"
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, MessageCircle, Radio, ShieldCheck } from "lucide-react"

import { PageHeader } from "@/components/app-shell/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { demoLeads, funnelData } from "@/lib/mock-data"

const priorities = [
  { lead: demoLeads[0], label: "Revisão pendente", reason: "Briefing preparado; ainda não enviado", icon: Clock3 },
  { lead: demoLeads[1], label: "SLA próximo", reason: "Falta confirmar a metragem antes de avançar", icon: MessageCircle },
  { lead: demoLeads[2], label: "Qualificação incompleta", reason: "O prazo continua como lacuna crítica", icon: AlertTriangle },
]

export default function DashboardPage() {
  const funnelMaximum = Math.max(...funnelData.map((item) => item.leads), 1)

  return <div className="space-y-6">
    <PageHeader eyebrow="Hoje · operação B2C" title="O que precisa de você" description="Prioridades demonstrativas ordenadas pelo próximo compromisso, não por um score isolado." />

    <Card className="overflow-hidden border-primary/25 bg-primary/[0.045] shadow-sm">
      <CardContent className="relative p-5 sm:p-7">
        <div aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-primary" />
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-primary"><span className="size-2 rounded-full bg-primary" />Atenção agora</div>
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">3 conversas pedem uma decisão humana</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">Há duas revisões de resposta e uma conversa perto do prazo interno. Nenhuma mensagem foi enviada.</p>
          </div>
          <Button asChild size="lg" className="min-h-11 shrink-0"><Link href="/app/inbox">Revisar na Inbox <ArrowRight aria-hidden="true" /></Link></Button>
        </div>
      </CardContent>
    </Card>

    <section aria-labelledby="priorities-title" className="grid gap-5 xl:grid-cols-[1.45fr_0.8fr]">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-4 border-b"><div><CardTitle id="priorities-title">Próximas ações</CardTitle><p className="mt-1 text-xs text-muted-foreground">Por prazo e risco operacional · dados fictícios</p></div><Badge variant="outline" className="font-mono tabular-nums">3 agora</Badge></CardHeader>
        <CardContent className="divide-y p-0">{priorities.map(({lead,label,reason,icon:Icon}) => <article key={lead.id} className="p-4 sm:p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-center"><span className="grid size-10 shrink-0 place-items-center rounded-xl border bg-muted/45"><Icon aria-hidden="true" className="size-4" /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{lead.next}</h3><Badge variant="secondary">{label}</Badge></div><p className="mt-1 text-sm text-muted-foreground">{lead.name} · {reason}</p></div><div className="flex items-center justify-between gap-4 sm:justify-end"><div className="text-left sm:text-right"><p className="font-mono text-xs font-medium tabular-nums">{lead.due}</p><p className="mt-1 text-xs text-muted-foreground">{lead.owner}</p></div><Button asChild variant="outline" size="sm" className="min-h-10"><Link href={`/app/leads/${lead.id}`} aria-label={`Revisar ${lead.name}`}>Revisar <ArrowRight aria-hidden="true" /></Link></Button></div></div></article>)}</CardContent>
      </Card>
      <Card><CardHeader className="border-b"><CardTitle>Proteções e conexão</CardTitle></CardHeader><CardContent className="divide-y p-0 text-sm"><StatusRow icon={Radio} label="Instagram" value="Não conectado" detail="Fixtures locais; sem conta Meta" /><StatusRow icon={ShieldCheck} label="Aprovação humana" value="Obrigatória" detail="Autonomia nível 3" positive /><StatusRow icon={CheckCircle2} label="Kill switch" value="Disponível" detail="Interrompe ações externas" positive /></CardContent></Card>
    </section>

    <section aria-labelledby="pulse-title" className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
      <Card><CardHeader><CardTitle id="pulse-title">Pulso demonstrativo</CardTitle><p className="text-xs text-muted-foreground">Amostra fictícia · últimos 7 dias</p></CardHeader><CardContent className="grid grid-cols-2 gap-x-5 gap-y-6"><Metric value="18" label="Novas DMs" detail="Base do funil" /><Metric value="8" label="Qualificadas" detail="44% das novas" /><Metric value="2" label="Propostas ganhas" detail="11% das novas" /><Metric value="94%" label="Dentro do SLA" detail="Indicador fictício" /></CardContent></Card>
      <Card><CardHeader><CardTitle>Onde as oportunidades estão</CardTitle><p className="text-xs text-muted-foreground">Contagem absoluta por etapa · barras partem de zero</p></CardHeader><CardContent><div className="space-y-4" role="img" aria-label="Funil demonstrativo: 18 novos, 12 em qualificação, 8 qualificados, 4 em proposta e 2 ganhos">{funnelData.map((item) => <div key={item.stage} className="grid grid-cols-[7.5rem_1fr_2rem] items-center gap-3 text-sm"><span className="truncate text-muted-foreground">{item.stage}</span><div className="h-2.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{width:`${(item.leads/funnelMaximum)*100}%`}} /></div><span className="text-right font-mono font-semibold tabular-nums">{item.leads}</span></div>)}</div><p className="mt-5 border-t pt-4 text-xs leading-5 text-muted-foreground">A largura compara cada etapa com a maior contagem (18). Não representa probabilidade de conversão.</p></CardContent></Card>
    </section>
  </div>
}

function StatusRow({icon:Icon,label,value,detail,positive=false}:{icon:typeof Radio;label:string;value:string;detail:string;positive?:boolean}) { return <div className="flex items-start gap-3 p-4 sm:p-5"><Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${positive?"text-emerald-600":"text-amber-600"}`} /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{label}</span><span className="text-xs font-medium">{value}</span></div><p className="mt-1 text-xs text-muted-foreground">{detail}</p></div></div> }
function Metric({value,label,detail}:{value:string;label:string;detail:string}) { return <div><p className="font-mono text-3xl font-semibold tracking-tight tabular-nums">{value}</p><p className="mt-1 text-sm font-medium">{label}</p><p className="mt-1 text-xs text-muted-foreground">{detail}</p></div> }
