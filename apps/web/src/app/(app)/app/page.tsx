import Link from "next/link"
import { ArrowRight, CheckCheck, Clock3, MessageCircle, Radar, Users } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
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
  const fresh = pipeline.entries.filter((entry) => entry.stage === "new")
  const won = pipeline.entries.filter((entry) => entry.stage === "won")
  const scheduled = pipeline.entries.filter((entry) => entry.next_action_at && !["won", "lost"].includes(entry.stage))
  const nextHref = fresh.length ? "/app/inbox?view=contacts" : "/app/hunter"
  const metrics = [
    { label: "Novos leads", value: pipeline.available ? fresh.length : "—", icon: Users },
    { label: "Follow-ups", value: pipeline.available ? scheduled.length : "—", icon: Clock3 },
    { label: "Conversas abertas", value: inbox.available ? inbox.conversations.length : "—", icon: MessageCircle },
    { label: "Ganhos", value: pipeline.available ? won.length : "—", icon: CheckCheck },
  ]
  const recent = [...pipeline.entries].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5)

  return <div className="kiara-dashboard space-y-5">
    {(!pipeline.available || !inbox.available) && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">Parte dos dados não pôde ser carregada. Os indicadores indisponíveis aparecem como “—”.</div>}
    <section className="kiara-dashboard-hero" aria-labelledby="dashboard-title">
      <div className="kiara-dashboard-copy">
        <p className="kiara-dashboard-eyebrow">Seu espaço comercial</p>
        <h1 id="dashboard-title">Transformando<br />oportunidades<br />em resultados.</h1>
        <p className="kiara-dashboard-lead">{fresh.length ? `Você tem ${fresh.length} ${fresh.length === 1 ? "lead novo" : "leads novos"} esperando uma primeira abordagem.` : "Encontre novos contatos e acompanhe cada oportunidade em um só lugar."}</p>
        <Button asChild size="lg" className="kiara-dashboard-cta"><Link href={nextHref}>{fresh.length ? "Começar minha fila" : "Pesquisar leads"}<ArrowRight className="size-4" /></Link></Button>
      </div>
      <div className="kiara-dashboard-planet" aria-hidden="true"><KiaraOrb size="lg" /></div>
      <div className="kiara-dashboard-metrics" aria-label="Indicadores da operação">
        {metrics.map(({ label, value, icon: Icon }) => <div key={label} className="kiara-dashboard-metric"><span className="kiara-dashboard-metric-icon"><Icon className="size-5" aria-hidden="true" /></span><div><p className="kiara-dashboard-metric-value">{value}</p><p className="kiara-dashboard-metric-label">{label}</p></div></div>)}
      </div>
    </section>
    <section className="kiara-dashboard-table" aria-labelledby="recent-title">
      <div className="kiara-dashboard-table-head"><h2 id="recent-title">Leads recentes</h2><div className="flex items-center gap-3"><RefreshWorkspace /><Link href="/app/inbox?view=contacts" className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">Ver todos <ArrowRight className="size-3.5" /></Link></div></div>
      {recent.length ? <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-sm"><thead><tr><th>Lead</th><th>Origem</th><th>Atualizado</th><th>Status</th></tr></thead><tbody>{recent.map((entry) => <tr key={entry.id}><td><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} className="font-semibold text-foreground hover:text-primary">{entry.consumer.display_name}</Link></td><td>{sourceLabels[entry.consumer.source ?? ""] ?? "CRM"}</td><td><time dateTime={entry.updated_at}>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(entry.updated_at))}</time></td><td><span className="kiara-dashboard-status">{pipelineStages.find((stage) => stage.id === entry.stage)?.label ?? entry.stage}</span></td></tr>)}</tbody></table></div> : <div className="kiara-dashboard-empty"><Radar className="size-5 text-primary" /><p>Seus primeiros leads aparecerão aqui depois de uma pesquisa.</p><Link href="/app/hunter" className="font-semibold text-primary hover:underline">Encontrar leads <ArrowRight className="inline size-3.5" /></Link></div>}
    </section>
  </div>
}
