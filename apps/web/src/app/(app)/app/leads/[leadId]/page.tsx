import Link from "next/link"
import { notFound } from "next/navigation"
import { PageHeader } from "@/components/app-shell/page-header"
import { LeadContactActions } from "@/components/app-shell/lead-contact-actions"
import { LeadActivityTimeline } from "@/components/app-shell/lead-activity-timeline"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { Button } from "@/components/ui/button"
import { getPipelineDTO } from "@/lib/api/pipeline-server"
import { pipelineStages, sourceLabels, websiteLabel } from "@/lib/api/pipeline"

export default async function LeadPage({ params }: { params: Promise<{ leadId: string }> }) {
  const { leadId } = await params
  const result = await getPipelineDTO().then((entries) => ({ entries, error: false })).catch(() => ({ entries: [], error: true }))
  if (result.error) return <div className="space-y-5"><PageHeader title="Contato indisponível" description="Não foi possível consultar o CRM agora." actions={<RefreshWorkspace />} /><p role="alert">Tente atualizar. Seus dados não foram apagados.</p></div>
  const entry = result.entries.find((item) => item.consumer.id === leadId)
  if (!entry) notFound()
  const consumer = entry.consumer
  return <div className="space-y-6"><PageHeader eyebrow={sourceLabels[consumer.source ?? ""] ?? "CRM"} title={consumer.display_name} description="Dados públicos da pesquisa, organizados para revisão comercial." actions={<Button asChild variant="outline"><Link href="/app/pipeline">Voltar ao Pipeline</Link></Button>} /><section className="max-w-3xl space-y-6 rounded-xl border bg-card p-6"><LeadContactActions entry={entry} /><dl className="grid gap-5 sm:grid-cols-2">{[
    ["Etapa", pipelineStages.find((stage) => stage.id === entry.stage)?.label], ["Telefone", consumer.phone || "Não informado"],
    ["WhatsApp", consumer.whatsapp_url ? "Link público encontrado" : "Não confirmado"], ["Website", websiteLabel(consumer.website_status)],
    ["Endereço", consumer.address || "Não informado"], ["Pesquisa de origem", consumer.research_query || "Não informada"],
  ].map(([label, value]) => <div key={label}><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-sm font-medium">{value}</dd></div>)}</dl><div className="border-t pt-5"><h2 className="text-sm font-semibold">Próxima ação</h2><p className="mt-2 text-sm text-muted-foreground">{entry.next_action || "Revisar contato antes de iniciar uma abordagem."}</p>{entry.next_action_at ? <p className="mt-1 text-xs text-primary">Agendada para {new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(entry.next_action_at))}</p> : null}</div><LeadActivityTimeline activities={entry.activities} /><p className="text-xs leading-5 text-muted-foreground">“Sem site informado” descreve a fonte consultada, não prova a inexistência de um site. Um contato público não representa consentimento nem uma conversa iniciada.</p></section></div>
}
