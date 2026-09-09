"use client"

import Link from "next/link"
import { useState } from "react"
import { MessageCircle, Search, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { InboxWorkspace } from "./inbox-workspace"
import { LeadContactActions } from "./lead-contact-actions"
import type { InboxConversationDTO } from "@/lib/api/inbox"
import { sourceLabels, websiteLabel, type PipelineEntry } from "@/lib/api/pipeline"

export function InboxHub({ conversations, entries, conversationError, prospectError, initialView }: {
  conversations: readonly InboxConversationDTO[]; entries: PipelineEntry[]; conversationError: string; prospectError: string; initialView: string
}) {
  const [query, setQuery] = useState("")
  const contacts = entries.filter((entry) => !["won", "lost"].includes(entry.stage))
  const filtered = contacts.filter((entry) => `${entry.consumer.display_name} ${entry.consumer.phone ?? ""}`.toLowerCase().includes(query.toLowerCase()))
  return <Tabs defaultValue={initialView === "contacts" ? "contacts" : "conversations"} className="gap-5">
    <TabsList className="h-11 w-full sm:w-fit"><TabsTrigger value="conversations" className="px-4"><MessageCircle />Conversas <span className="ml-1 text-xs tabular-nums">{conversationError ? "—" : conversations.length}</span></TabsTrigger><TabsTrigger value="contacts" className="px-4"><Users />Prospectados <span className="ml-1 text-xs tabular-nums">{prospectError ? "—" : contacts.length}</span></TabsTrigger></TabsList>
    <TabsContent value="conversations">
      {conversationError ? <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{conversationError}</div> : <InboxWorkspace initialConversations={conversations} />}
      <p className="mt-4 text-xs leading-5 text-muted-foreground">Esta aba contém conversas reais recebidas pelo Instagram conectado. Contatos descobertos no Hunter ficam em Prospectados; abrir um WhatsApp não sincroniza mensagens externas.</p>
    </TabsContent>
    <TabsContent value="contacts" className="space-y-4">
      <div className="flex flex-col justify-between gap-4 rounded-xl border bg-card p-5 sm:flex-row sm:items-center"><div><h2 className="font-semibold">Contatos para sua próxima abordagem</h2><p className="mt-1 max-w-xl text-sm leading-6 text-muted-foreground">Leads do Pipeline, sem conversas inventadas. WhatsApp aparece somente quando um link público foi encontrado. Nenhuma mensagem é enviada automaticamente.</p></div><Button asChild variant="outline"><Link href="/app/pipeline">Ver Pipeline</Link></Button></div>
      {prospectError && <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{prospectError}</div>}
      <div className="relative"><Search className="absolute top-3 left-3 size-4 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 pl-9" placeholder="Buscar um contato" aria-label="Buscar prospectados" /></div>
      {!filtered.length && !prospectError ? <div className="rounded-xl border border-dashed p-10 text-center"><Users className="mx-auto size-6 text-muted-foreground" /><h3 className="mt-3 font-semibold">{query ? "Nenhum contato corresponde à busca" : "Nenhum contato prospectado ainda"}</h3><p className="mt-2 text-sm text-muted-foreground">Novos leads aprovados na pesquisa do Hunter aparecerão aqui e no Pipeline.</p><Button asChild className="mt-5"><Link href="/app/hunter">Pesquisar leads</Link></Button></div> : <div className="divide-y overflow-hidden rounded-xl border bg-card">{filtered.map((entry) => <article key={entry.id} className="flex flex-col gap-4 p-5 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} className="break-words font-semibold hover:text-primary">{entry.consumer.display_name}</Link><p className="mt-1 text-xs text-muted-foreground">{sourceLabels[entry.consumer.source ?? ""] ?? "CRM"} · {websiteLabel(entry.consumer.website_status)}</p>{entry.consumer.phone && <p className="mt-2 text-sm tabular-nums">{entry.consumer.phone}{!entry.consumer.whatsapp_url && <span className="ml-2 text-xs text-muted-foreground">WhatsApp não confirmado</span>}</p>}</div><div className="shrink-0"><LeadContactActions entry={entry} /></div></article>)}</div>}
    </TabsContent>
  </Tabs>
}
