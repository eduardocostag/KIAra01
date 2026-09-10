import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, Globe2, MapPin, MessageCircle, Sparkles } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"
import { LeadContactActions } from "@/components/app-shell/lead-contact-actions"
import { LeadActivityTimeline } from "@/components/app-shell/lead-activity-timeline"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { Button } from "@/components/ui/button"
import { getPipelineDTO } from "@/lib/api/pipeline-server"
import { pipelineStages, sourceLabels, websiteLabel } from "@/lib/api/pipeline"

export default async function LeadPage({ params }: { params: Promise<{ leadId: string }> }) {
  const { leadId } = await params
  const result = await getPipelineDTO().then((entries) => ({ entries, error: false })).catch(() => ({ entries: [], error: true }))
  if (result.error) return <div className="kiara-soft-panel p-8"><h1 className="kiara-editorial text-3xl">Contato indisponível</h1><p className="mt-3 text-muted-foreground">Não foi possível consultar o CRM agora. Seus dados não foram apagados.</p><div className="mt-5"><RefreshWorkspace /></div></div>
  const entry = result.entries.find((item) => item.consumer.id === leadId)
  if (!entry) notFound()
  const consumer = entry.consumer
  const facts = [["Etapa", pipelineStages.find((stage) => stage.id === entry.stage)?.label], ["Número para WhatsApp", consumer.phone || "Não informado"], ["WhatsApp", consumer.whatsapp_url ? "Link público encontrado" : "Não confirmado"], ["Website", websiteLabel(consumer.website_status)], ["Endereço", consumer.address || "Não informado"], ["Pesquisa de origem", consumer.research_query || "Não informada"]]
  return <div className="space-y-6"><Button asChild variant="ghost" className="-ml-3"><Link href="/app/pipeline"><ArrowLeft />Voltar à fila</Link></Button><section className="kiara-copilot-stage overflow-hidden rounded-[30px] border bg-card shadow-[var(--shadow-2)]"><div className="grid lg:grid-cols-[minmax(0,1fr)_320px]"><div className="p-7 sm:p-10"><p className="text-xs font-semibold uppercase tracking-[.16em] text-primary">{sourceLabels[consumer.source ?? ""] ?? "CRM"}</p><h1 className="kiara-editorial mt-3 max-w-3xl text-4xl leading-tight sm:text-5xl">{consumer.display_name}</h1><p className="mt-4 max-w-xl text-sm leading-6 text-muted-foreground">Dados públicos organizados para uma decisão comercial responsável.</p><div className="mt-7"><LeadContactActions entry={entry} /></div></div><div className="flex flex-col items-center justify-center border-t bg-primary/5 p-8 text-center lg:border-l lg:border-t-0"><KiaraOrb size="lg" active /><p className="mt-6 flex items-center gap-2 text-xs font-semibold text-primary"><Sparkles className="size-3.5" />Próximo movimento</p><p className="kiara-editorial mt-2 text-2xl leading-tight">{entry.next_action || "Revise o contexto antes da primeira abordagem."}</p></div></div></section><div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]"><section className="rounded-[26px] bg-card p-6 shadow-[var(--shadow-1)] sm:p-8"><h2 className="kiara-editorial text-2xl">Inteligência do contato</h2><dl className="mt-7 grid gap-6 sm:grid-cols-2">{facts.map(([label, value]) => <div key={label} className="border-b pb-4"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 break-words text-sm font-medium">{value}</dd></div>)}</dl><div className="mt-6 flex flex-wrap gap-3 text-xs text-muted-foreground">{consumer.phone && <span className="flex items-center gap-2"><MessageCircle className="size-4 text-primary" />Contato público</span>}{consumer.address && <span className="flex items-center gap-2"><MapPin className="size-4 text-primary" />Localização identificada</span>}<span className="flex items-center gap-2"><Globe2 className="size-4 text-primary" />{websiteLabel(consumer.website_status)}</span></div></section><section className="rounded-[26px] bg-card p-6 shadow-[var(--shadow-1)]"><h2 className="kiara-editorial text-2xl">Pulso recente</h2><div className="mt-5"><LeadActivityTimeline activities={entry.activities} /></div></section></div></div>
}
