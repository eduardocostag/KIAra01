"use client"

import Link from "next/link"
import { useState } from "react"
import { ArrowUpRight, Globe2, MapPin, MessageCircle, Phone, Search, Sparkles, Users } from "lucide-react"
import { SourceMark } from "@/components/brand/source-mark"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { InboxWorkspace } from "./inbox-workspace"
import { LeadContactActions } from "./lead-contact-actions"
import type { InboxConversationDTO } from "@/lib/api/inbox"
import { leadDisplayName, sourceLabels, websiteLabel, type PipelineEntry } from "@/lib/api/pipeline"
import "./inbox-hub.css"

export function InboxHub({ conversations, entries, conversationError, prospectError, initialView }: {
  conversations: readonly InboxConversationDTO[]; entries: PipelineEntry[]; conversationError: string; prospectError: string; initialView: string
}) {
  const [query, setQuery] = useState("")
  const [view, setView] = useState(initialView === "contacts" ? "contacts" : "conversations")
  const [selectedContactId, setSelectedContactId] = useState(entries[0]?.id ?? "")
  const contacts = entries.filter((entry) => !["won", "lost"].includes(entry.stage))
  const filtered = contacts.filter((entry) => `${leadDisplayName(entry.consumer)} ${entry.consumer.display_name} ${entry.consumer.phone ?? ""}`.toLowerCase().includes(query.toLowerCase()))
  const selectedContact = contacts.find((entry) => entry.id === selectedContactId) ?? filtered[0] ?? contacts[0]
  return <Tabs value={view} onValueChange={setView} className="inbox-premium gap-5">
    <div className="kiara-inbox-toolbar"><TabsList className="h-11 w-full sm:w-fit"><TabsTrigger value="conversations" className="px-4"><MessageCircle />Conversas <span className="ml-1 text-xs tabular-nums">{conversationError ? "—" : conversations.length}</span></TabsTrigger><TabsTrigger value="contacts" className="px-4"><Users />Contatos <span className="ml-1 text-xs tabular-nums">{prospectError ? "—" : contacts.length}</span></TabsTrigger></TabsList>{view === "contacts" ? <div className="kiara-inbox-search"><Search aria-hidden="true" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-11 pl-10" placeholder="Buscar um contato" aria-label="Buscar prospectados" /></div> : null}</div>
    <TabsContent value="conversations">
      {conversationError ? <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{conversationError}</div> : <InboxWorkspace initialConversations={conversations} />}
    </TabsContent>
    <TabsContent value="contacts" className="space-y-4">
      {prospectError && <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{prospectError}</div>}
      {!filtered.length && !prospectError ? <div className="rounded-xl border border-dashed p-10 text-center"><Users className="mx-auto size-6 text-muted-foreground" /><h3 className="mt-3 font-semibold">{query ? "Nenhum contato corresponde à busca" : "Nenhum contato ainda"}</h3><Button asChild className="mt-5"><Link href="/app/hunter">Pesquisar leads</Link></Button></div> : selectedContact ? <div className="kiara-contact-workspace"><aside className="kiara-contact-list" aria-label="Clientes encontrados"><div className="kiara-contact-list-title"><strong>Clientes encontrados</strong><span>{filtered.length}</span></div>{filtered.map((entry) => { const active = entry.id === selectedContact.id; const source = sourceLabels[entry.consumer.source ?? ""] ?? "CRM"; const name = leadDisplayName(entry.consumer); return <button key={entry.id} type="button" className={active ? "is-active" : ""} aria-pressed={active} onClick={() => setSelectedContactId(entry.id)}><span className="kiara-contact-initial">{name.replace(/^@/, "").slice(0,1).toUpperCase()}</span><span><strong>{name}</strong><small>{source} · {entry.consumer.phone || "Sem telefone"}</small></span></button>})}</aside><ContactDossier entry={selectedContact} /></div> : null}
    </TabsContent>
  </Tabs>
}

function ContactDossier({ entry }: { entry: PipelineEntry }) {
  const consumer = entry.consumer
  const displayName = leadDisplayName(consumer)
  const source = sourceLabels[consumer.source ?? ""] ?? "CRM"
  const kind = /instagram/i.test((consumer.source ?? "") + source) ? "instagram" : /maps|google/i.test((consumer.source ?? "") + source) ? "maps" : "web"
  const info = [
    { label: "Fonte", value: source, icon: Sparkles },
    { label: "Telefone", value: consumer.phone || "Não informado", icon: Phone },
    { label: "WhatsApp", value: consumer.whatsapp_url ? "Link público encontrado" : "Não confirmado", icon: MessageCircle },
    { label: "Site", value: websiteLabel(consumer.website_status), icon: Globe2 },
    { label: "Endereço", value: consumer.address || "Não informado", icon: MapPin },
  ]
  return <section className="kiara-contact-dossier" aria-label={`Detalhes de ${displayName}`}><header><div className="kiara-contact-identity"><span><SourceMark kind={kind} /></span><div><div><h2>{displayName}</h2><span className="kiara-contact-status">Novo</span></div><p>{consumer.research_query || source}</p></div></div><div className="kiara-contact-header-actions"><LeadContactActions entry={entry} /><Link href={`/app/leads/${encodeURIComponent(consumer.id)}`}>Abrir ficha<ArrowUpRight /></Link></div></header><nav aria-label="Seções do contato"><span>Visão geral</span><a href="#contact-actions">Ações</a><a href="#contact-context">Contexto</a></nav><div className="kiara-contact-grid"><section><h3>Informações</h3><dl>{info.map(({ label, value, icon: Icon }) => <div key={label}><dt><Icon />{label}</dt><dd>{value}</dd></div>)}</dl></section><section id="contact-actions"><h3>Ações rápidas</h3><div className="kiara-contact-quick-actions"><div><span><MessageCircle /></span><div><strong>Iniciar conversa</strong><small>Prepare uma mensagem personalizada acima</small></div></div><Link href={`/app/leads/${encodeURIComponent(consumer.id)}`}><span><Sparkles /></span><div><strong>Abrir ficha completa</strong><small>Consulte evidências e atividades</small></div><ArrowUpRight /></Link><Link href="/app/hunter"><span><Search /></span><div><strong>Nova pesquisa</strong><small>Encontre outras oportunidades</small></div><ArrowUpRight /></Link></div></section></div><section id="contact-context" className="kiara-contact-description"><h3>Descrição</h3><p>{consumer.research_query ? `Contato encontrado na pesquisa “${consumer.research_query}”.` : "Contato identificado em uma fonte pública."}{consumer.address ? ` Localização informada: ${consumer.address}.` : ""} Revise os dados antes de iniciar a abordagem.</p></section></section>
}
