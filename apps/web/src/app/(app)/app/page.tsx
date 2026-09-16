import Link from "next/link"
import { ArrowRight, AudioLines, ChartNoAxesColumnIncreasing, CheckCircle2, Clock3, MessageCircle, Radar, Search, TrendingUp } from "lucide-react"
import { OrbitScene } from "@/components/brand/orbit-scene"
import { SourceMark } from "@/components/brand/source-mark"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { Button } from "@/components/ui/button"
import { getInboxDTO } from "@/lib/api/inbox"
import { getPipelineDTO } from "@/lib/api/pipeline-server"
import { leadDisplayName, pipelineStages, sourceLabels } from "@/lib/api/pipeline"

function relativeTime(value: string, now: number) {
  const minutes = Math.max(0, Math.floor((now - new Date(value).getTime()) / 60000))
  if (!Number.isFinite(minutes)) return "—"
  if (minutes < 1) return "Agora"
  if (minutes < 60) return `Há ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Há ${hours} h`
  const days = Math.floor(hours / 24)
  return `Há ${days} ${days === 1 ? "dia" : "dias"}`
}

export default async function DashboardPage() {
  const [pipeline, inbox] = await Promise.all([
    getPipelineDTO().then((entries) => ({ entries, available: true })).catch(() => ({ entries: [], available: false })),
    getInboxDTO().then((data) => ({ conversations: data.conversations, available: true })).catch(() => ({ conversations: [], available: false })),
  ])
  const fresh = pipeline.entries.filter((entry) => entry.stage === "new")
  const scheduled = pipeline.entries.filter((entry) => entry.next_action_at && !["won", "lost"].includes(entry.stage))
  const now = new Date().getTime()
  const activities = pipeline.entries.flatMap((entry) => entry.activities ?? [])
  const contacts = activities.filter((activity) => activity.status === "sent").length
  const replies = activities.filter((activity) => activity.status === "replied").length
  const wins = pipeline.entries.filter((entry) => entry.stage === "won").length
  const conversionRate = pipeline.entries.length ? Math.round((wins / pipeline.entries.length) * 100) : 0
  const nextHref = fresh.length ? "/app/inbox?view=contacts" : "/app/hunter"
  const metrics = [
    { label: "Novos leads", value: pipeline.available ? fresh.length : "—", icon: ChartNoAxesColumnIncreasing, href: "/app/inbox?view=contacts" },
    { label: "Follow-ups", value: pipeline.available ? scheduled.length : "—", icon: Clock3, href: "/app/followups" },
    { label: "Pipeline", value: pipeline.available ? pipeline.entries.length : "—", icon: ChartNoAxesColumnIncreasing, href: "/app/pipeline" },
  ]
  const recent = [...pipeline.entries].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5)

  const dateLabel = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", timeZone: "America/Sao_Paulo" }).format(new Date())
  return <div className="kiara-dashboard kiara-orbit-dashboard">
    {(!pipeline.available || !inbox.available) && <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">Parte dos dados não pôde ser carregada. Os indicadores indisponíveis aparecem como “—”.</div>}
    <section className="kiara-dashboard-hero" aria-labelledby="dashboard-title">
      <div className="kiara-dashboard-copy">
        <p className="kiara-dashboard-eyebrow">{dateLabel}</p>
        <h1 id="dashboard-title"><span>Converse.</span><span>Entenda.</span><span className="kiara-dashboard-gradient-word">Conquiste.</span></h1>
        <p className="kiara-dashboard-lead">{fresh.length ? `Você tem ${fresh.length} ${fresh.length === 1 ? "lead novo" : "leads novos"} esperando uma primeira abordagem.` : "A Kiara reúne oportunidades reais e organiza o próximo passo da sua operação."}</p>
        <Button asChild size="lg" className="kiara-dashboard-cta"><Link href={nextHref}>{fresh.length ? "Começar minha fila" : "Pesquisar leads"}<ArrowRight className="size-4" /></Link></Button>
        <div className="kiara-dashboard-capabilities" aria-label="Acessos rápidos"><Link href="/app/hunter"><span><Search className="size-3.5" /></span>Hunter</Link><Link href="/app/inbox"><span><AudioLines className="size-3.5" /></span>Leads</Link></div>
      </div>
      <div className="kiara-dashboard-planet" aria-hidden="true"><OrbitScene /></div>
      <div className="kiara-dashboard-metrics" role="group" aria-label="Indicadores da operação">
        {metrics.map(({ label, value, icon: Icon, href }) => <Link key={label} href={href} className="kiara-dashboard-metric"><span className="kiara-dashboard-metric-icon"><Icon className="size-5" aria-hidden="true" /></span><div><p className="kiara-dashboard-metric-value">{value}</p><p className="kiara-dashboard-metric-label">{label}</p></div></Link>)}
      </div>
    </section>
    <section className="kiara-dashboard-roi" aria-labelledby="roi-title">
      <div className="kiara-dashboard-roi-head">
        <div><p className="kiara-dashboard-section-eyebrow"><TrendingUp className="size-3.5" />Impacto comercial</p><h2 id="roi-title">ROI da operação</h2><p>Resultado calculado a partir dos leads e atividades registrados neste workspace.</p></div>
        <Link href="/app/settings" className="kiara-dashboard-roi-link">Configurar ticket médio <ArrowRight className="size-3.5" /></Link>
      </div>
      <div className="kiara-dashboard-roi-grid">
        {[{ label: "Leads gerados", value: pipeline.available ? pipeline.entries.length : "—", detail: "No Pipeline", icon: Radar }, { label: "Contatos registrados", value: pipeline.available ? contacts : "—", detail: "Envios confirmados", icon: MessageCircle }, { label: "Respostas", value: pipeline.available ? replies : "—", detail: "Atividades recebidas", icon: CheckCircle2 }, { label: "Ganhos", value: pipeline.available ? wins : "—", detail: pipeline.available ? `${conversionRate}% de conversão` : "Dados indisponíveis", icon: TrendingUp }].map(({ label, value, detail, icon: Icon }) => <div key={label} className="kiara-dashboard-roi-stat"><span><Icon className="size-4" /></span><div><strong>{value}</strong><p>{label}</p><small>{detail}</small></div></div>)}
      </div>
      <div className="kiara-dashboard-roi-foot"><span>Receita atribuída</span><strong>Não calculada</strong><small>Informe o ticket médio e registre os ganhos para acompanhar o retorno financeiro.</small></div>
    </section>
    <section className="kiara-dashboard-table" aria-labelledby="recent-title">
      <div className="kiara-dashboard-table-head"><h2 id="recent-title">Leads recentes</h2><div className="kiara-dashboard-table-actions"><RefreshWorkspace /><Link href="/app/inbox?view=contacts" className="kiara-dashboard-see-all">Ver todos <ArrowRight className="size-3.5" /></Link></div></div>
      {recent.length ? <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-sm"><caption className="sr-only">Leads recentes com origem e status</caption><thead><tr><th scope="col">Lead</th><th scope="col">Origem</th><th scope="col">Tempo</th><th scope="col">Status</th></tr></thead><tbody>{recent.map((entry) => {
        const source = entry.consumer.source ?? ""
        const sourceLabel = sourceLabels[source] ?? "Web pública"
        const kind = /instagram/i.test(source + sourceLabel) ? "instagram" : /maps|google/i.test(source + sourceLabel) ? "maps" : "web"
        return <tr key={entry.id}><td><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} className="kiara-dashboard-lead-link"><span className="kiara-dashboard-lead-name">{leadDisplayName(entry.consumer)}</span></Link></td><td><span className="kiara-dashboard-source"><span className={`kiara-dashboard-source-icon kiara-dashboard-source-${kind}`}><SourceMark kind={kind} /></span>{sourceLabel}</span></td><td><time dateTime={entry.updated_at}>{relativeTime(entry.updated_at, now)}</time></td><td><span className="kiara-dashboard-status">{pipelineStages.find((stage) => stage.id === entry.stage)?.label ?? entry.stage}</span></td></tr>
      })}</tbody></table></div> : <div className="kiara-dashboard-empty"><Radar className="size-5 text-primary" /><p>Seus primeiros leads aparecerão aqui depois de uma pesquisa.</p><Link href="/app/hunter" className="font-semibold text-primary hover:underline">Encontrar leads <ArrowRight className="inline size-3.5" /></Link></div>}
    </section>
  </div>
}
