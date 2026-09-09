import Link from "next/link"
import { ArrowRight, CheckCheck, MessageCircle, Radar, Sparkles, Users } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { PageHeader } from "@/components/app-shell/page-header"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { Button } from "@/components/ui/button"
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
    { label: "Leads", value: pipeline.available ? pipeline.entries.length : "—", icon: Users },
    { label: "Em andamento", value: pipeline.available ? active.length : "—", icon: Radar },
    { label: "Conversas", value: inbox.available ? inbox.conversations.length : "—", icon: MessageCircle },
    { label: "Ganhos", value: pipeline.available ? won.length : "—", icon: CheckCheck },
  ]
  const nextHref = fresh.length ? "/app/pipeline" : "/app/hunter"
  return <div className="space-y-7">
    <PageHeader eyebrow="Bom trabalho começa com clareza" title="Visão geral" description="A Kiara organiza sua operação e mostra somente o próximo movimento que importa." actions={<RefreshWorkspace />} />
    {(!pipeline.available || !inbox.available) && <div role="alert" className="rounded-2xl border border-destructive/25 bg-destructive/5 p-4 text-sm">Parte dos dados não pôde ser carregada. Os indicadores indisponíveis aparecem como “—”.</div>}
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicadores da operação">
      {metrics.map(({ label, value, icon: Icon }) => <div key={label} className="kiara-soft-panel flex items-center justify-between p-5"><div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p></div><span className="grid size-10 place-items-center rounded-full bg-primary/8 text-primary"><Icon className="size-4" /></span></div>)}
    </section>
    <section className="kiara-copilot-stage kiara-soft-panel grid min-h-[390px] overflow-hidden lg:grid-cols-[minmax(220px,.7fr)_minmax(390px,1.45fr)_minmax(230px,.75fr)]">
      <div className="border-b p-6 lg:border-b-0 lg:border-r"><p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">Pulso de hoje</p><div className="mt-6 space-y-5"><Pulse label="Novos para conhecer" value={fresh.length} /><Pulse label="Follow-ups agendados" value={scheduled.length} /><Pulse label="Conversas abertas" value={inbox.conversations.length} /></div></div>
      <div className="flex flex-col items-center justify-center px-7 py-12 text-center"><KiaraOrb size="lg" active /><p className="mt-8 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.2em] text-primary"><Sparkles className="size-3.5" />Recomendação da Kiara</p><h2 className="kiara-editorial mt-3 max-w-lg text-3xl leading-tight sm:text-4xl">{fresh.length ? `Você tem ${fresh.length} ${fresh.length === 1 ? "lead novo" : "leads novos"} esperando uma primeira abordagem.` : "Vamos encontrar sua próxima oportunidade?"}</h2><p className="mt-4 max-w-md text-sm leading-6 text-muted-foreground">{fresh.length ? "Eu organizei a fila. Revise o primeiro contato e abra o WhatsApp quando estiver pronto." : "Descreva o público, a região e os critérios. Eu cuido da organização dos resultados."}</p><Button asChild size="lg" className="mt-7 rounded-full px-6"><Link href={nextHref}>{fresh.length ? "Começar minha fila" : "Pesquisar leads"}<ArrowRight /></Link></Button></div>
      <div className="border-t p-6 lg:border-l lg:border-t-0"><div className="flex items-center justify-between"><p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">Leads recentes</p><Link className="text-xs font-medium text-primary" href="/app/pipeline">Ver todos</Link></div><div className="mt-5 space-y-2">{pipeline.entries.slice(0, 4).map((entry) => <Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} key={entry.id} className="block rounded-2xl border bg-background/75 p-4 transition hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-sm"><p className="truncate text-sm font-semibold">{entry.consumer.display_name}</p><div className="mt-2 flex justify-between text-[11px] text-muted-foreground"><span>{sourceLabels[entry.consumer.source ?? ""] ?? "CRM"}</span><span>{pipelineStages.find((stage) => stage.id === entry.stage)?.label}</span></div></Link>)}{!pipeline.entries.length && <p className="rounded-2xl border border-dashed p-5 text-xs leading-5 text-muted-foreground">Seus primeiros leads aparecerão aqui depois de uma pesquisa.</p>}</div></div>
    </section>
  </div>
}

function Pulse({ label, value }: { label: string; value: number }) { return <div className="border-b pb-4 last:border-0"><p className="text-2xl font-semibold tabular-nums">{value}</p><p className="mt-1 text-xs text-muted-foreground">{label}</p></div> }
