import Link from "next/link"
import { ArrowLeft, ArrowUpRight, Globe2, MapPin, MessageCircle, NotebookPen, Radar, Search, Star, UserRound } from "lucide-react"
import { SourceMark } from "@/components/brand/source-mark"
import { LeadContactActions } from "@/components/app-shell/lead-contact-actions"
import { LeadCompanyPanel } from "@/components/app-shell/lead-company-panel"
import { type PipelineEntry, leadDisplayName, pipelineStages, safePublicUrl, sourceLabels, websiteLabel } from "@/lib/api/pipeline"
import "@/app/(app)/app/(leads-module)/leads/[leadId]/lead-detail.css"

/** One lead: contact actions, facts, company data, fit and timeline. */
export function LeadDetail({ entry }: { entry: PipelineEntry }) {
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
    ...(typeof consumer.rating === "number" ? [{ label: "Google", value: `Nota ${consumer.rating.toFixed(1)}${typeof consumer.user_rating_count === "number" ? ` · ${consumer.user_rating_count} avaliações` : ""}`, icon: Star }] : []),
    { label: "Endereço", value: consumer.address || "Não informado", icon: MapPin },
    { label: "Pesquisa", value: consumer.research_query || "Não informada", icon: Search },
  ]

  return <main className="kiara-lead-detail">
    <nav className="kiara-lead-breadcrumb" aria-label="Caminho"><Link href="/app">Workspace</Link><span aria-hidden="true">›</span><Link href="/app/pipeline?view=contacts">Leads</Link><span aria-hidden="true">›</span><span>Detalhes</span></nav>
    <div className="kiara-lead-topline"><Link href="/app/pipeline?view=contacts" className="kiara-lead-back"><ArrowLeft className="size-4" />Voltar</Link><div className="kiara-lead-top-actions"><LeadContactActions entry={entry} /></div></div>
    <header className="kiara-lead-heading"><span className="kiara-lead-mark"><SourceMark kind={kind} /></span><div className="min-w-0"><div className="kiara-lead-title-row"><h1>{displayName}</h1><span className="kiara-lead-stage">{stage}</span></div><p>{sourceLabel}</p></div></header>
    <div id="overview" className="kiara-lead-main-grid">
      <section className="kiara-lead-panel" aria-labelledby="lead-information-title"><h2 id="lead-information-title">Informações</h2><dl className="kiara-lead-facts">{facts.map(({ label, value, icon: Icon }) => <div key={label}><dt><Icon className="size-4" aria-hidden="true" />{label}</dt><dd>{value}</dd></div>)}</dl>{websiteUrl ? <a href={websiteUrl} target="_blank" rel="noreferrer" className="kiara-lead-inline-link">Abrir site identificado<ArrowUpRight className="size-4" /></a> : null}</section>
      <section className="kiara-lead-panel" aria-labelledby="lead-actions-title"><h2 id="lead-actions-title">Ações rápidas</h2><div className="kiara-lead-action-list">{sourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer"><span><Globe2 className="size-4" /></span><div><strong>Abrir fonte</strong><small>Confira o dado público original</small></div><ArrowUpRight className="size-4" /></a> : null}<Link href="/app/pipeline?view=contacts"><span><UserRound className="size-4" /></span><div><strong>Ver outros contatos</strong><small>Volte para a sua fila de leads</small></div><ArrowUpRight className="size-4" /></Link><Link href={`/app/pipeline?view=contacts&contact=${encodeURIComponent(entry.id)}`}><span><NotebookPen className="size-4" /></span><div><strong>Anotações</strong><small>{consumer.notes?.trim() ? "Consulte ou edite a anotação" : "Registre uma anotação neste cliente"}</small></div><ArrowUpRight className="size-4" /></Link></div></section>
    </div>
    <LeadCompanyPanel leadId={consumer.id} initialCompany={consumer.company ?? null} initialFit={consumer.fit ?? null} />
    <section id="context" className="kiara-lead-panel kiara-lead-context" aria-labelledby="lead-context-title"><h2 id="lead-context-title">Contexto</h2><p>{consumer.research_query ? `Encontrado na pesquisa “${consumer.research_query}”.` : "Lead identificado em uma fonte pública."}{consumer.address ? ` Localização informada: ${consumer.address}.` : ""} Revise a fonte antes de iniciar uma abordagem.</p></section>
  </main>
}
