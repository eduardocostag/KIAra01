"use client"

import Link from "next/link"
import { useState } from "react"
import { ArrowUpRight, AtSign, Check, Columns3, FileText, Globe2, List, Loader2, MapPin, MessageCircle, NotebookPen, Phone, Search, Sparkles, Users } from "lucide-react"
import { SourceMark } from "@/components/brand/source-mark"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { LeadContactActions } from "./lead-contact-actions"
import { PipelineBoard } from "./pipeline-board"
import { instagramProfileUrl, leadDisplayName, parsePipelineEntry, requestPipeline, sourceLabels, websiteLabel, whatsappComposerUrl, type PipelineEntry } from "@/lib/api/pipeline"
import "./inbox-hub.css"

export function InboxHub({ entries: initialEntries, prospectError, initialView, initialContactId }: { entries: PipelineEntry[]; prospectError: string; initialView: string; initialContactId: string }) {
  const [entries, setEntries] = useState(initialEntries)
  const [query, setQuery] = useState("")
  const normalizedView = initialView === "pipeline" || initialView === "notes" || initialView === "conversations" ? (initialView === "conversations" ? "notes" : initialView) : "contacts"
  const requestedContact = initialEntries.find((entry) => entry.id === initialContactId || entry.consumer.id === initialContactId)
  const [view, setView] = useState(normalizedView)
  const [selectedContactId, setSelectedContactId] = useState(requestedContact?.id ?? entries[0]?.id ?? "")
  const [draftNoteId, setDraftNoteId] = useState(normalizedView === "notes" ? requestedContact?.id ?? "" : "")
  const contacts = entries.filter((entry) => !["won", "lost"].includes(entry.stage))
  const filtered = contacts.filter((entry) => `${leadDisplayName(entry.consumer)} ${entry.consumer.display_name} ${entry.consumer.phone ?? ""}`.toLowerCase().includes(query.toLowerCase()))
  const selectedContact = contacts.find((entry) => entry.id === selectedContactId) ?? filtered[0] ?? contacts[0]
  const annotatedContacts = contacts.filter((entry) => entry.consumer.notes?.trim())
  const noteContact = contacts.find((entry) => entry.id === draftNoteId) ?? annotatedContacts.find((entry) => entry.id === selectedContactId) ?? annotatedContacts[0]
  const annotatedCount = annotatedContacts.length

  return <Tabs value={view} onValueChange={setView} className="inbox-premium gap-5">
    <TabsList aria-label="Visualização dos leads" className="grid h-auto w-full grid-cols-3 rounded-xl border bg-card/70 p-1 sm:w-fit sm:min-w-[430px]">
      <TabsTrigger value="contacts" className="h-10 gap-2 rounded-lg"><List aria-hidden="true" />Lista <span className="hidden text-[10px] tabular-nums text-muted-foreground sm:inline">{contacts.length}</span></TabsTrigger>
      <TabsTrigger value="pipeline" className="h-10 gap-2 rounded-lg"><Columns3 aria-hidden="true" />Pipeline</TabsTrigger>
      <TabsTrigger value="notes" className="h-10 gap-2 rounded-lg"><NotebookPen aria-hidden="true" />Anotações <span className="hidden text-[10px] tabular-nums text-muted-foreground sm:inline">{annotatedCount}</span></TabsTrigger>
    </TabsList>
    <div className="kiara-inbox-toolbar">{view === "contacts" ? <div className="kiara-inbox-search"><Search aria-hidden="true" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="h-11 pl-10" placeholder="Buscar um contato" aria-label="Buscar prospectados" /></div> : null}</div>
    <TabsContent value="notes">
      {prospectError ? <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{prospectError}</div> : <NotesWorkspace entries={annotatedContacts} selectedEntry={noteContact} onSelect={(id) => { setDraftNoteId(""); setSelectedContactId(id) }} onSaved={(saved) => { setDraftNoteId(""); setSelectedContactId(saved.id); setEntries((current) => current.map((entry) => entry.id === saved.id ? saved : entry)) }} />}
    </TabsContent>
    <TabsContent value="contacts" className="space-y-4">
      {prospectError ? <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{prospectError}</div> : null}
      {!filtered.length && !prospectError ? <div className="rounded-xl border border-dashed p-10 text-center"><Users className="mx-auto size-6 text-muted-foreground" /><h3 className="mt-3 font-semibold">{query ? "Nenhum contato corresponde à busca" : "Nenhum contato ainda"}</h3><Button asChild className="mt-5"><Link href="/app/hunter">Pesquisar leads</Link></Button></div> : selectedContact ? <div className="kiara-contact-workspace"><ContactList entries={filtered} selectedId={selectedContact.id} onSelect={setSelectedContactId} /><ContactDossier entry={selectedContact} onOpenNotes={() => { setDraftNoteId(selectedContact.id); setView("notes") }} /></div> : null}
    </TabsContent>
    <TabsContent value="pipeline">
      {prospectError ? <div role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{prospectError}</div> : <PipelineBoard initialEntries={entries} />}
    </TabsContent>
  </Tabs>
}

function ContactList({ entries, selectedId, onSelect }: { entries: PipelineEntry[]; selectedId: string; onSelect: (id: string) => void }) {
  return <aside className="kiara-contact-list" aria-label="Clientes encontrados">
    <div className="kiara-contact-list-title"><strong>Clientes encontrados</strong><span>{entries.length}</span></div>
    {entries.map((entry) => {
      const active = entry.id === selectedId
      const source = sourceLabels[entry.consumer.source ?? ""] ?? "CRM"
      const name = leadDisplayName(entry.consumer)
      return <button key={entry.id} type="button" className={active ? "is-active" : ""} aria-pressed={active} onClick={() => onSelect(entry.id)}><span className="kiara-contact-initial">{name.replace(/^@/, "").slice(0, 1).toUpperCase()}</span><span><strong>{name}</strong><small>{source} · {entry.consumer.phone || "Sem telefone"}</small></span></button>
    })}
  </aside>
}

function NotesWorkspace({ entries, selectedEntry, onSelect, onSaved }: { entries: PipelineEntry[]; selectedEntry: PipelineEntry | undefined; onSelect: (id: string) => void; onSaved: (entry: PipelineEntry) => void }) {
  if (!selectedEntry) return <div className="rounded-xl border border-dashed p-10 text-center"><NotebookPen className="mx-auto size-6 text-muted-foreground" /><h3 className="mt-3 font-semibold">Nenhuma anotação salva</h3><p className="mt-2 text-sm text-muted-foreground">Use a ação “Anotações” na ficha de um cliente para registrar a primeira.</p></div>
  return <div className="kiara-contact-workspace kiara-notes-workspace"><ContactList entries={entries} selectedId={selectedEntry.id} onSelect={onSelect} /><NotesEditor key={selectedEntry.id} entry={selectedEntry} onSaved={onSaved} /></div>
}

function NotesEditor({ entry, onSaved }: { entry: PipelineEntry; onSaved: (entry: PipelineEntry) => void }) {
  const [notes, setNotes] = useState(entry.consumer.notes ?? "")
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle")
  const [message, setMessage] = useState("")
  const changed = notes.trim() !== (entry.consumer.notes ?? "").trim()

  async function persist(target: PipelineEntry) {
    return parsePipelineEntry(await requestPipeline(`/api/pipeline/${encodeURIComponent(target.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ notes: notes.trim() || null }) }))
  }

  async function save() {
    if (!changed || saving) return
    setSaving(true); setStatus("idle"); setMessage("")
    try {
      const saved = await persist(entry)
      onSaved(saved); setNotes(saved.consumer.notes ?? ""); setStatus("saved"); setMessage("Anotação salva neste cliente.")
    } catch (error) {
      setStatus("error"); setMessage(error instanceof Error ? error.message : "Não foi possível salvar a anotação.")
    } finally { setSaving(false) }
  }

  const name = leadDisplayName(entry.consumer)
  return <section className="kiara-notes-editor" aria-labelledby="contact-notes-title">
    <header><span><FileText aria-hidden="true" /></span><div><p>Anotações do cliente</p><h2 id="contact-notes-title">{name}</h2></div></header>
    <div className="kiara-notes-field"><label htmlFor={`contact-notes-${entry.id}`}>Registre contexto, preferências e próximos passos</label><Textarea id={`contact-notes-${entry.id}`} value={notes} onChange={(event) => { setNotes(event.target.value); setStatus("idle"); setMessage("") }} maxLength={5000} rows={12} placeholder="Ex.: Prefere contato pela manhã. Demonstrou interesse no plano anual..." /><div><span>{notes.length.toLocaleString("pt-BR")} / 5.000</span><Button type="button" onClick={() => void save()} disabled={!changed || saving}>{saving ? <Loader2 className="animate-spin" /> : status === "saved" ? <Check /> : <NotebookPen />}{saving ? "Salvando" : "Salvar anotação"}</Button></div>{message ? <p role={status === "error" ? "alert" : "status"} className={status === "error" ? "is-error" : "is-saved"}>{message}</p> : null}</div>
  </section>
}

function ContactDossier({ entry, onOpenNotes }: { entry: PipelineEntry; onOpenNotes: () => void }) {
  const consumer = entry.consumer
  const displayName = leadDisplayName(consumer)
  const source = sourceLabels[consumer.source ?? ""] ?? "CRM"
  const kind = /instagram/i.test((consumer.source ?? "") + source) ? "instagram" : /maps|google/i.test((consumer.source ?? "") + source) ? "maps" : "web"
  const whatsapp = whatsappComposerUrl(consumer.phone, consumer.whatsapp_url, "")
  const instagram = instagramProfileUrl(consumer.instagram_username)
  const info = [{ label: "Fonte", value: source, icon: Sparkles }, { label: "Telefone", value: consumer.phone || "Não informado", icon: Phone }, { label: "WhatsApp", value: consumer.whatsapp_url ? "Link público encontrado" : "Não confirmado", icon: MessageCircle }, { label: "Site", value: websiteLabel(consumer.website_status), icon: Globe2 }, { label: "Endereço", value: consumer.address || "Não informado", icon: MapPin }]
  return <section className="kiara-contact-dossier" aria-label={`Detalhes de ${displayName}`}>
    <header><div className="kiara-contact-identity"><span><SourceMark kind={kind} /></span><div><div><h2 title={displayName}>{displayName}</h2><span className="kiara-contact-status">Novo</span></div><p>{consumer.research_query || source}</p></div></div><div className="kiara-contact-header-actions"><LeadContactActions entry={entry} /></div></header>
    <div className="kiara-contact-grid"><section><h3>Informações</h3><dl>{info.map(({ label, value, icon: Icon }) => <div key={label}><dt><Icon />{label}</dt><dd>{value}</dd></div>)}</dl></section><section id="contact-actions"><h3>Ações rápidas</h3><div className="kiara-contact-quick-actions">
      <DropdownMenu><DropdownMenuTrigger asChild><button type="button" disabled={!whatsapp && !instagram}><span><MessageCircle /></span><div><strong>Iniciar conversa</strong><small>{whatsapp || instagram ? "Abrir o canal sem mensagem pronta" : "Nenhum canal direto disponível"}</small></div><ArrowUpRight /></button></DropdownMenuTrigger><DropdownMenuContent align="start" className="w-64"><DropdownMenuLabel>Conversar diretamente</DropdownMenuLabel><DropdownMenuSeparator />{whatsapp ? <DropdownMenuItem asChild><a href={whatsapp.url} target="_blank" rel="noreferrer"><MessageCircle className="text-emerald-500" />Abrir WhatsApp<ArrowUpRight className="ml-auto" /></a></DropdownMenuItem> : null}{instagram ? <DropdownMenuItem asChild><a href={instagram} target="_blank" rel="noreferrer"><AtSign className="text-fuchsia-500" />Abrir Instagram<ArrowUpRight className="ml-auto" /></a></DropdownMenuItem> : null}</DropdownMenuContent></DropdownMenu>
      <Link href={`/app/leads/${encodeURIComponent(consumer.id)}`}><span><Sparkles /></span><div><strong>Abrir ficha completa</strong><small>Consulte evidências e atividades</small></div><ArrowUpRight /></Link>
      <button type="button" onClick={onOpenNotes}><span><NotebookPen /></span><div><strong>Anotações</strong><small>{consumer.notes?.trim() ? "Consultar ou editar a anotação" : "Registrar uma anotação neste cliente"}</small></div><ArrowUpRight /></button>
    </div></section></div>
    <section id="contact-context" className="kiara-contact-description"><h3>Descrição</h3><p>{consumer.research_query ? `Contato encontrado na pesquisa “${consumer.research_query}”.` : "Contato identificado em uma fonte pública."}{consumer.address ? ` Localização informada: ${consumer.address}.` : ""} Revise os dados antes de iniciar a abordagem.</p></section>
  </section>
}
