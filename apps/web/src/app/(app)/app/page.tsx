import Link from "next/link"
import { ArrowRight, CheckCheck, Clock3, Columns3, MessageCircle, Radar, Users } from "lucide-react"
import { PageHeader } from "@/components/app-shell/page-header"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { getInboxDTO } from "@/lib/api/inbox"
import { getPipelineDTO } from "@/lib/api/pipeline-server"
import { pipelineStages, sourceLabels } from "@/lib/api/pipeline"

export default async function DashboardPage() {
  const [pipeline, inbox] = await Promise.all([
    getPipelineDTO().then((entries) => ({ entries, available: true })).catch(() => ({ entries: [], available: false })),
    getInboxDTO().then((data) => ({ conversations: data.conversations, available: true })).catch(() => ({ conversations: [], available: false })),
  ])
  const active = pipeline.entries.filter((entry) => !["won", "lost"].includes(entry.stage))
  const fresh = pipeline.entries.filter((entry) => entry.stage === "new")
  const won = pipeline.entries.filter((entry) => entry.stage === "won")
  const scheduled = pipeline.entries.filter((entry) => entry.next_action_at && !["won", "lost"].includes(entry.stage))
  const metrics = [
    { title: "Leads no CRM", value: pipeline.available ? pipeline.entries.length : "—", detail: "Base real do workspace", icon: Users },
    { title: "Em andamento", value: pipeline.available ? active.length : "—", detail: "Do primeiro contato à negociação", icon: Columns3 },
    { title: "Conversas", value: inbox.available ? inbox.conversations.length : "—", detail: "Recebidas pelo Instagram", icon: MessageCircle },
    { title: "Negócios ganhos", value: pipeline.available ? won.length : "—", detail: "Marcados como ganhos no Pipeline", icon: CheckCheck },
    { title: "Follow-ups", value: pipeline.available ? scheduled.length : "—", detail: "Acompanhamentos agendados", icon: Clock3 },
  ]
  return <div className="space-y-6">
    <PageHeader eyebrow="Seu workspace · B2B e B2C" title="Visão geral" description="Da pesquisa à próxima conversa. Uma visão real da sua operação comercial." actions={<RefreshWorkspace />} />
    {(!pipeline.available || !inbox.available) && <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">Não foi possível carregar {!pipeline.available && !inbox.available ? "o CRM e as conversas" : !pipeline.available ? "o CRM" : "as conversas"}. Os dados indisponíveis aparecem como “—”, não como zero. Tente atualizar.</div>}
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Indicadores da operação">{metrics.map(({ title, value, detail, icon: Icon }) => <Card key={title} className="shadow-none"><CardContent className="p-5"><div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">{title}</p><Icon className="size-4 text-muted-foreground" /></div><p className="mt-4 text-3xl font-semibold tracking-tight tabular-nums">{value}</p><p className="mt-2 text-xs text-muted-foreground">{detail}</p></CardContent></Card>)}</section>
    <section className="relative flex flex-col justify-between gap-6 overflow-hidden rounded-xl bg-sidebar p-6 text-sidebar-foreground sm:p-8 lg:flex-row lg:items-center"><div className="relative"><p className="text-xs font-medium uppercase tracking-widest text-sidebar-foreground/65">Seu próximo movimento</p><h2 className="mt-3 text-2xl font-semibold tracking-tight">{fresh.length ? `${fresh.length} novos leads para conhecer.` : "Encontre quem faz sentido para o seu negócio."}</h2><p className="mt-3 max-w-xl text-sm leading-6 text-sidebar-foreground/75">{fresh.length ? "Os contatos encontrados pelo Hunter já estão no seu Pipeline. Revise os dados e escolha sua próxima abordagem." : "Defina o público, escolha as fontes e filtre pelos dados que realmente importam."}</p></div><Button asChild size="lg" className="shrink-0"><Link href={fresh.length ? "/app/pipeline" : "/app/hunter"}>{fresh.length ? "Revisar leads" : "Abrir Hunter"}<ArrowRight /></Link></Button></section>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
      <section className="overflow-hidden rounded-xl border bg-card"><header className="flex items-center justify-between border-b p-5"><h2 className="font-semibold">Leads atualizados</h2><Link href="/app/pipeline" className="flex items-center gap-1 text-xs font-medium text-primary">Ver todos <ArrowRight className="size-3" /></Link></header>{pipeline.entries.length ? <div className="divide-y">{pipeline.entries.slice(0, 5).map((entry) => <Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} key={entry.id} className="flex items-center justify-between gap-3 p-5 transition-colors hover:bg-muted/40"><div className="min-w-0"><p className="truncate text-sm font-medium">{entry.consumer.display_name}</p><p className="mt-1 text-xs text-muted-foreground">{sourceLabels[entry.consumer.source ?? ""] ?? "CRM"}</p></div><span className="shrink-0 rounded-md bg-muted px-2 py-1 text-xs">{pipelineStages.find((stage) => stage.id === entry.stage)?.label}</span></Link>)}</div> : <div className="px-6 py-12 text-center"><Radar className="mx-auto size-6 text-muted-foreground" /><p className="mt-3 text-sm text-muted-foreground">{pipeline.available ? "Os leads aprovados nas novas pesquisas aparecerão aqui." : "CRM temporariamente indisponível."}</p></div>}</section>
      <section className="rounded-xl border bg-card p-5"><h2 className="font-semibold">Distribuição do Pipeline</h2><div className="mt-5 space-y-4">{pipelineStages.map((stage) => {
        const count = pipeline.entries.filter((entry) => entry.stage === stage.id).length
        return <div key={stage.id}><div className="mb-2 flex items-center justify-between text-xs"><span className="text-muted-foreground">{stage.label}</span><span className="tabular-nums">{pipeline.available ? count : "—"}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true"><div className="h-full rounded-full bg-primary" style={{ width: `${pipeline.entries.length ? count / pipeline.entries.length * 100 : 0}%` }} /></div></div>
      })}</div><p className="mt-5 border-t pt-4 text-xs leading-5 text-muted-foreground">Descobrir um contato não significa que ele foi contatado ou qualificado. As etapas são atualizadas no Pipeline.</p></section>
    </div>
  </div>
}
