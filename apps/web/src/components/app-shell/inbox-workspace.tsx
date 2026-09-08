"use client"

import Link from "next/link"
import { useMemo, useState, useSyncExternalStore } from "react"
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  FileEdit,
  LockKeyhole,
  MessageCircle,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import type { InboxConversationDTO } from "@/lib/api/inbox"
import { cn } from "@/lib/utils"

const filters = ["Todas", "Novas", "Aprovação", "Aguardando cliente"] as const
type ComposerPhase = "empty" | "draft" | "approval" | "approved"
type ComposerSession = { draft: string; phase: ComposerPhase }

function subscribeDesktop(callback: () => void) {
  const query = window.matchMedia("(min-width: 1280px)")
  query.addEventListener("change", callback)
  return () => query.removeEventListener("change", callback)
}

function getDesktopSnapshot() {
  return window.matchMedia("(min-width: 1280px)").matches
}

function getServerSnapshot() {
  return false
}

function initials(name: string) {
  return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()
}

function listHref(id: string, query: string, filter: string) {
  const search = new URLSearchParams()
  if (query) search.set("q", query)
  if (filter !== "Todas") search.set("filter", filter)
  const suffix = search.size ? `?${search.toString()}` : ""
  return `/app/inbox/${encodeURIComponent(id)}${suffix}`
}

function inboxHref(query: string, filter: string) {
  const search = new URLSearchParams()
  if (query) search.set("q", query)
  if (filter !== "Todas") search.set("filter", filter)
  return search.size ? `/app/inbox?${search.toString()}` : "/app/inbox"
}

function StatusBadge({ status }: { status: string }) {
  const review = status === "Aprovação"
  const waiting = status === "Aguardando cliente"
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1 rounded-full border-transparent px-2 text-[10px]",
        review && "bg-[var(--warning-subtle)] text-[var(--warning)]",
        waiting && "bg-muted text-muted-foreground",
        !review && !waiting && "bg-[var(--info-subtle)] text-[var(--info)]",
      )}
    >
      <CircleDot aria-hidden="true" className="size-2.5" />
      {status}
    </Badge>
  )
}

function ConversationList({
  conversations,
  selectedId,
  query,
  filter,
  onQuery,
  onFilter,
  onDesktopSelect,
}: {
  conversations: readonly InboxConversationDTO[]
  selectedId: string
  query: string
  filter: string
  onQuery: (value: string) => void
  onFilter: (value: string) => void
  onDesktopSelect?: (id: string) => void
}) {
  const unreadTotal = conversations.reduce(
    (total, conversation) => total + conversation.unread,
    0,
  )

  return (
    <section className="flex min-h-0 flex-col bg-card" aria-label="Lista de conversas">
      <div className="space-y-3 border-b p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Conversas</h2>
            <p className="text-xs text-muted-foreground">Prioridade e contexto em um só lugar</p>
          </div>
          <Badge className="rounded-full">
            {unreadTotal > 0 ? `${unreadTotal} não lida${unreadTotal === 1 ? "" : "s"}` : "Em dia"}
          </Badge>
        </div>
        <div className="relative">
          <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(event) => onQuery(event.target.value)} className="h-11 pl-9 xl:h-10" placeholder="Buscar pessoa ou mensagem" aria-label="Buscar na Inbox" />
        </div>
        <div className="flex gap-1 overflow-x-auto pb-1" role="group" aria-label="Filtrar conversas">
          {filters.map((item) => (
            <Button key={item} type="button" size="sm" variant={filter === item ? "secondary" : "ghost"} className="h-10 rounded-full px-3 xl:h-8" aria-pressed={filter === item} onClick={() => onFilter(item)}>
              {item}
            </Button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto [content-visibility:auto]">
        {conversations.length ? conversations.map((conversation) => {
          const selected = selectedId === conversation.id
          return (
            <Link
              key={conversation.id}
              href={listHref(conversation.id, query, filter)}
              onClick={(event) => {
                if (onDesktopSelect) {
                  event.preventDefault()
                  onDesktopSelect(conversation.id)
                }
              }}
              aria-current={selected ? "page" : undefined}
              className={cn(
                "group relative flex min-h-24 items-start gap-3 border-b px-4 py-4 outline-none transition-colors hover:bg-muted/55 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
                selected && "bg-[var(--brand-subtle)] before:absolute before:inset-y-3 before:left-0 before:w-[3px] before:rounded-r-full before:bg-primary",
              )}
            >
              <span className="relative grid size-10 shrink-0 place-items-center rounded-xl border bg-muted text-xs font-semibold text-foreground">
                {initials(conversation.name)}
                {conversation.unread > 0 ? <span className="absolute -right-1 -top-1 grid min-w-4 place-items-center rounded-full bg-[var(--info)] px-1 text-[9px] font-semibold text-white" aria-label={`${conversation.unread} não lidas`}>{conversation.unread}</span> : null}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-2">
                  <span className="truncate text-sm font-semibold">{conversation.name}</span>
                  <time className="font-mono text-[10px] text-muted-foreground">{conversation.time}</time>
                </span>
                <span className="mt-1 block truncate text-xs leading-5 text-muted-foreground">{conversation.excerpt}</span>
                <span className="mt-2 flex items-center justify-between gap-2">
                  <StatusBadge status={conversation.status} />
                  <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </span>
              </span>
            </Link>
          )
        }) : (
          <div className="grid min-h-48 place-items-center p-6 text-center">
            <div><Search aria-hidden="true" className="mx-auto mb-3 size-5 text-muted-foreground" /><p className="text-sm font-medium">Nenhuma conversa encontrada</p><p className="mt-1 text-xs text-muted-foreground">Ajuste a busca ou escolha outro filtro.</p></div>
          </div>
        )}
      </div>
    </section>
  )
}

function QualificationPanel({ conversation }: { conversation: InboxConversationDTO }) {
  return (
    <aside className="space-y-5 bg-card p-5" aria-label={`Qualificação de ${conversation.name}`}>
      <div className="rounded-2xl bg-[var(--brand-subtle)] p-4">
        <div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">Leitura Kiara</p><span className="font-mono text-2xl font-semibold">{conversation.score || "—"}</span></div>
        <Progress value={conversation.score} className="mt-3" aria-label={`Score de qualificação ${conversation.score} de 100`} />
        <div className="mt-3 flex items-center justify-between text-xs"><span className="font-medium">{conversation.intent}</span><span className="text-muted-foreground">{conversation.confidence}</span></div>
        {conversation.qualifiedAt ? <p className="mt-2 font-mono text-[10px] text-muted-foreground">Calculado {conversation.qualifiedAt}</p> : null}
      </div>
      <div className="rounded-xl border border-primary/20 bg-primary/[0.045] p-4">
        <p className="flex items-center gap-2 text-sm font-semibold"><Target aria-hidden="true" className="size-4 text-primary" />Próxima ação</p>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">{conversation.nextAction}</p>
      </div>
      <div><h3 className="text-sm font-semibold">Confirmado</h3>{conversation.facts.length ? <ul className="mt-2 space-y-2">{conversation.facts.map((fact) => <li key={fact} className="flex gap-2 text-xs leading-5 text-muted-foreground"><CheckCircle2 aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-[var(--success)]" />{fact}</li>)}</ul> : <p className="mt-2 text-xs leading-5 text-muted-foreground">A API ainda não forneceu fatos estruturados.</p>}</div>
      <div><h3 className="text-sm font-semibold">Falta saber</h3>{conversation.gaps.length ? <ul className="mt-2 space-y-2">{conversation.gaps.map((gap) => <li key={gap} className="flex gap-2 text-xs leading-5 text-muted-foreground"><CircleDot aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-[var(--warning)]" />{gap}</li>)}</ul> : <p className="mt-2 text-xs leading-5 text-muted-foreground">Nenhuma lacuna estruturada foi retornada pela API.</p>}</div>
      <div className="rounded-xl border p-4"><p className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck aria-hidden="true" className="size-4 text-[var(--success)]" />Canal permitido</p><p className="mt-2 text-xs leading-5 text-muted-foreground">DM iniciada pela pessoa. Toda resposta continua sujeita à política e à aprovação humana.</p></div>
      <Button type="button" variant="ghost" className="w-full text-destructive"><LockKeyhole />Revisar bloqueio</Button>
    </aside>
  )
}

function Composer({ conversation, session, onChange }: { conversation: InboxConversationDTO; session: ComposerSession; onChange: (session: ComposerSession) => void }) {
  if (session.phase === "empty") return (
    <div className="space-y-3 border-t bg-[var(--surface-2)] p-4">
      <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold">Próximo passo seguro</p><p className="mt-1 text-xs text-muted-foreground">Nenhum rascunho foi retornado pela API.</p></div><Badge variant="outline">Não enviado</Badge></div>
      <Button type="button" className="h-11 w-full" disabled={!conversation.suggestedDraft} onClick={() => onChange({ draft: conversation.suggestedDraft, phase: "draft" })}><Sparkles />Preparar resposta</Button>
      <p className="text-xs text-muted-foreground">A criação persistente ainda não está conectada nesta tela.</p>
    </div>
  )
  return (
    <div className="space-y-3 border-t bg-[var(--surface-2)] p-4">
      <div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold uppercase tracking-[0.12em]">Rascunho assistido</p><Badge variant={session.phase === "approval" || session.phase === "approved" ? "secondary" : "outline"} aria-live="polite">{session.phase === "draft" ? "Ainda não enviado" : session.phase === "approved" ? "Aprovado · não enviado" : "Aguardando aprovação"}</Badge></div>
      <Textarea value={session.draft} disabled={session.phase !== "draft"} onChange={(event) => onChange({ draft: event.target.value, phase: "draft" })} className="min-h-24 resize-none bg-background" aria-label={`Rascunho de resposta para ${conversation.name}`} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><ShieldCheck aria-hidden="true" className="size-3.5" />Envio continua desativado</p>
        {session.phase === "draft" ? <div className="flex gap-2"><Button type="button" variant="ghost" onClick={() => onChange({ draft: "", phase: "empty" })}><FileEdit />Descartar</Button><Button type="button" disabled={!session.draft.trim()} onClick={() => onChange({ ...session, phase: "approval" })}><Check />Solicitar aprovação</Button></div> : <Button type="button" variant="outline" onClick={() => onChange({ ...session, phase: "draft" })}><FileEdit />Editar rascunho</Button>}
      </div>
    </div>
  )
}

function ConversationThread({ conversation, session, onSession, mobileBackHref }: { conversation: InboxConversationDTO; session: ComposerSession; onSession: (session: ComposerSession) => void; mobileBackHref?: string }) {
  return (
    <section className="flex min-h-0 flex-col bg-card" aria-label={`Conversa com ${conversation.name}`}>
      <header className="flex min-h-16 items-center gap-3 border-b bg-card/95 p-3 backdrop-blur-sm">
        {mobileBackHref ? <Button asChild variant="ghost" size="icon" className="size-11 xl:hidden"><Link href={mobileBackHref} aria-label="Voltar para a Inbox"><ArrowLeft /></Link></Button> : null}
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-[var(--brand-subtle)] text-xs font-bold text-primary">{initials(conversation.name)}</span>
        <div className="min-w-0 flex-1"><h2 className="truncate text-sm font-semibold">{conversation.name}</h2><p className="flex items-center gap-1.5 truncate text-xs text-muted-foreground"><MessageCircle aria-hidden="true" className="size-3" />{conversation.handle} · inbound</p></div>
        <Sheet><SheetTrigger asChild><Button type="button" variant="outline" className="h-11 xl:hidden"><Target />Qualificação {conversation.score}</Button></SheetTrigger><SheetContent className="w-[min(92vw,390px)] overflow-y-auto"><SheetHeader><SheetTitle>Qualificação de {conversation.name}</SheetTitle><SheetDescription>Leitura, evidências e próxima ação desta conversa.</SheetDescription></SheetHeader><QualificationPanel conversation={conversation} /></SheetContent></Sheet>
        <Button variant="outline" asChild className="hidden xl:inline-flex"><Link href={`/app/leads/${encodeURIComponent(conversation.id)}`}>Dossiê<ChevronRight /></Link></Button>
      </header>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-[var(--surface-2)]/60 p-4 sm:p-6">
        <p className="text-center font-mono text-[10px] text-muted-foreground">Hoje · horário de Brasília</p>
        {conversation.messages.length ? conversation.messages.map((message) => (
          <article key={message.id} className={cn("max-w-[86%]", message.from === "operator" && "ml-auto")} aria-label={`${message.from === "operator" ? "Operador" : conversation.name}, ${message.time}`}>
            <p className="mb-1 px-1 text-[10px] font-medium text-muted-foreground">{message.from === "operator" ? "Você" : conversation.name}</p>
            <div className={cn("rounded-2xl border bg-background px-4 py-3 shadow-[var(--shadow-1)]", message.from === "operator" ? "rounded-br-md bg-[var(--brand-subtle)]" : "rounded-bl-md")}><p className="text-sm leading-6">{message.text}</p><time className="mt-1 block text-right font-mono text-[10px] text-muted-foreground">{message.time}</time></div>
          </article>
        )) : <p className="rounded-xl border border-dashed p-5 text-center text-sm text-muted-foreground">Nenhuma mensagem disponível nesta conversa.</p>}
        <div className="relative rounded-xl border border-primary/20 bg-[var(--brand-subtle)] p-4 before:absolute before:inset-y-3 before:left-0 before:w-[3px] before:rounded-r-full before:bg-primary">
          <p className="flex items-center gap-2 text-xs font-semibold text-primary"><Sparkles aria-hidden="true" className="size-3.5" />Análise da Kiara</p><p className="mt-2 text-sm leading-6"><strong>{conversation.intent}.</strong> {conversation.gaps[0] ? `Ainda falta confirmar: ${conversation.gaps[0].toLowerCase()}.` : "A API não retornou lacunas estruturadas."}</p>
        </div>
      </div>
      <Composer conversation={conversation} session={session} onChange={onSession} />
    </section>
  )
}

export function InboxWorkspace({ initialConversations, initialConversationId, initialQuery = "", initialFilter = "Todas" }: { initialConversations: readonly InboxConversationDTO[]; initialConversationId?: string; initialQuery?: string; initialFilter?: string }) {
  const isDesktop = useSyncExternalStore(subscribeDesktop, getDesktopSnapshot, getServerSnapshot)
  const [selected, setSelected] = useState(initialConversationId ?? initialConversations[0]?.id ?? "")
  const [query, setQuery] = useState(initialQuery)
  const [filter, setFilter] = useState(filters.includes(initialFilter as (typeof filters)[number]) ? initialFilter : "Todas")
  const [sessions, setSessions] = useState<Record<string, ComposerSession>>(() => Object.fromEntries(initialConversations.map((conversation) => [conversation.id, conversation.savedDraft ? { draft: conversation.savedDraft.text, phase: conversation.savedDraft.status === "approved" ? "approved" : "draft" } : { draft: "", phase: "empty" }])))
  const conversations = useMemo(() => initialConversations.filter((conversation) => (filter === "Todas" || conversation.status === filter) && `${conversation.name} ${conversation.handle} ${conversation.excerpt}`.toLowerCase().includes(query.trim().toLowerCase())), [filter, initialConversations, query])
  const active = initialConversations.find((conversation) => conversation.id === selected) ?? initialConversations[0]

  if (!active) return <div className="rounded-2xl border bg-card p-8 text-center"><UserRound aria-hidden="true" className="mx-auto mb-3 size-6 text-muted-foreground" /><p className="text-sm font-medium">Nenhuma conversa disponível</p><p className="mt-1 text-xs text-muted-foreground">Novas DMs aparecerão aqui quando forem recebidas.</p></div>

  const session = sessions[active.id] ?? { draft: "", phase: "empty" as const }
  const updateSession = (next: ComposerSession) => setSessions((current) => ({ ...current, [active.id]: next }))
  const list = <ConversationList conversations={conversations} selectedId={active.id} query={query} filter={filter} onQuery={setQuery} onFilter={setFilter} onDesktopSelect={isDesktop ? setSelected : undefined} />

  if (!isDesktop && !initialConversationId) return <div className="min-h-[calc(100dvh-12rem)] overflow-hidden rounded-2xl border bg-card shadow-[var(--shadow-1)]">{list}</div>
  if (!isDesktop) return <div className="min-h-[calc(100dvh-8rem)] overflow-hidden rounded-2xl border bg-card shadow-[var(--shadow-1)]"><ConversationThread conversation={active} session={session} onSession={updateSession} mobileBackHref={inboxHref(query, filter)} /></div>

  return (
    <div className="h-[calc(100dvh-12rem)] min-h-[660px] max-h-[940px] overflow-hidden rounded-[var(--radius-panel)] border bg-card shadow-[var(--shadow-1)]">
      <div className="grid h-full grid-cols-[minmax(320px,360px)_minmax(480px,1fr)_minmax(320px,360px)] divide-x">
        {list}
        <ConversationThread conversation={active} session={session} onSession={updateSession} />
        <div className="min-h-0 overflow-y-auto"><QualificationPanel conversation={active} /></div>
      </div>
    </div>
  )
}
