import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, ArrowUpRight, Globe2, MapPin, MessageCircle, NotebookPen, Radar, Search, UserRound } from "lucide-react"
import { SourceMark } from "@/components/brand/source-mark"
import { LeadContactActions } from "@/components/app-shell/lead-contact-actions"
import { RefreshWorkspace } from "@/components/app-shell/refresh-workspace"
import { getPipelineDTO } from "@/lib/api/pipeline-server"
import { leadDisplayName, pipelineStages, safePublicUrl, sourceLabels, websiteLabel } from "@/lib/api/pipeline"
import "./lead-detail.css"

export default async function LeadPage({ params }: { params: Promise<{ leadId: string }> }) {
  const { leadId } = await params
  const result = await getPipelineDTO().then((entries) => ({ entries, error: false })).catch(() => ({ entries: [], error: true }))
  if (result.error) return <div className="kiara-soft-panel p-8"><h1 className="text-2xl font-semibold">Contato indisponível</h1><p className="mt-3 text-muted-foreground">Não foi possível consultar os leads agora. Seus dados não foram apagados.</p><div className="mt-5"><RefreshWorkspace /></div></div>
  const entry = result.entries.find((item) => item.consumer.id === leadId)
  if (!entry) notFound()

  const consumer = entry.consumer
  const displayName = leadDisplayName(consumer)
  const sourceLabel = sourceLabels[consumer.source ?? ""] ?? "Web pública"
  const kind = /instagram/i.test((consumer.source ?? "") + sourceLabel) ? "instagram" : /maps|google/i.test((consumer.source ?? "") + sourceLabel) ? "maps" : "web"
  const sourceUrl = safePublicUrl(consumer.source_url)
  const websiteUrl = safePublicUrl(consumer.website_url)
  const stage = pipelineStages.find((item) => item.id === entry.stage)?.label ?? entry.stage
  const facts = [
    { label: "Fonte", value: sourceLabel, icon: Radar },
    { label: "Telefone", value: consumer.phone || "Não informado", icon: MessageCircle },
    { label: "WhatsApp", value: consumer.whatsapp_url ? "Link público encontrado" : "Não confirmado", icon: MessageCircle },
    { label: "Site", value: websiteLabel(consumer.website_status), icon: Globe2 },
    { label: "Endereço", value: consumer.address || "Não informado", icon: MapPin },
    { label: "Pesquisa", value: consumer.research_query || "Não informada", icon: Search },
  ]

  return <main className="kiara-lead-detail">
    <nav className="kiara-lead-breadcrumb" aria-label="Caminho"><Link href="/app">Workspace</Link><span aria-hidden="true">›</span><Link href="/app/inbox?view=contacts">Leads</Link><span aria-hidden="true">›</span><span>Detalhes</span></nav>
    <div className="kiara-lead-topline"><Link href="/app/inbox?view=contacts" className="kiara-lead-back"><ArrowLeft className="size-4" />Voltar</Link><div className="kiara-lead-top-actions"><LeadContactActions entry={entry} /></div></div>
    <header className="kiara-lead-heading"><span className="kiara-lead-mark"><SourceMark kind={kind} /></span><div className="min-w-0"><div className="kiara-lead-title-row"><h1>{displayName}</h1><span className="kiara-lead-stage">{stage}</span></div><p>{sourceLabel}</p></div></header>
    <div id="overview" className="kiara-lead-main-grid">
      <section className="kiara-lead-panel" aria-labelledby="lead-information-title"><h2 id="lead-information-title">Informações</h2><dl className="kiara-lead-facts">{facts.map(({ label, value, icon: Icon }) => <div key={label}><dt><Icon className="size-4" aria-hidden="true" />{label}</dt><dd>{value}</dd></div>)}</dl>{websiteUrl ? <a href={websiteUrl} target="_blank" rel="noreferrer" className="kiara-lead-inline-link">Abrir site identificado<ArrowUpRight className="size-4" /></a> : null}</section>
      <section className="kiara-lead-panel" aria-labelledby="lead-actions-title"><h2 id="lead-actions-title">Ações rápidas</h2><div className="kiara-lead-action-list">{sourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer"><span><Globe2 className="size-4" /></span><div><strong>Abrir fonte</strong><small>Confira o dado público original</small></div><ArrowUpRight className="size-4" /></a> : null}<Link href="/app/inbox?view=contacts"><span><UserRound className="size-4" /></span><div><strong>Ver outros contatos</strong><small>Volte para a sua fila de leads</small></div><ArrowUpRight className="size-4" /></Link><Link href={`/app/inbox?view=notes&contact=${encodeURIComponent(entry.id)}`}><span><NotebookPen className="size-4" /></span><div><strong>Anotações</strong><small>{consumer.notes?.trim() ? "Consulte ou edite a anotação" : "Registre uma anotação neste cliente"}</small></div><ArrowUpRight className="size-4" /></Link></div></section>
    </div>
    <section id="context" className="kiara-lead-panel kiara-lead-context" aria-labelledby="lead-context-title"><h2 id="lead-context-title">Contexto</h2><p>{consumer.research_query ? `Encontrado na pesquisa “${consumer.research_query}”.` : "Lead identificado em uma fonte pública."}{consumer.address ? ` Localização informada: ${consumer.address}.` : ""} Revise a fonte antes de iniciar uma abordagem.</p></section>
  </main>
}
