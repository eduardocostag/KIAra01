"use client"

import Link from "next/link"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, ArrowUp, Bot, Cable, Hand, Info, LoaderCircle, MessageCircle, RefreshCw, Search, Workflow } from "lucide-react"
import { ImmersiveShell } from "@/components/app-shell/immersive-shell"
import { WhatsAppConnectionPanel } from "@/components/app-shell/whatsapp-gateway-workspace"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { channelLabels, deliveryLabels, sendOutcome, temperatureLabels, type InboxConversationDTO } from "@/lib/api/inbox-contract"
import { cn } from "@/lib/utils"

const footerLink = "flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-sm text-sidebar-foreground/65 hover:bg-sidebar-foreground/5 hover:text-sidebar-foreground"

function initials(name: string) {
  const parts = name.replace(/^@/, "").split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase()
}

function WhatsAppFooter({ onConnection }: { onConnection: () => void }) {
  return <>
    <button type="button" onClick={onConnection} className={footerLink}><Cable className="size-4" aria-hidden="true" />Conexão</button>
    <Link href="/app/whatsapp/automacao" className={footerLink}><Workflow className="size-4" aria-hidden="true" />Automação</Link>
  </>
}

function ConnectionDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
      <DialogHeader><DialogTitle>Conexão do WhatsApp</DialogTitle><DialogDescription>Estado da sessão e resumo do contato autorizado.</DialogDescription></DialogHeader>
      {open ? <WhatsAppConnectionPanel /> : null}
    </DialogContent>
  </Dialog>
}

/** Conversation-first WhatsApp workspace: list on the left, thread in the center, composer at the bottom. */
export function WhatsAppInbox({ conversations, canSend = false, initialId = "", loadError = "" }: { conversations: readonly InboxConversationDTO[]; canSend?: boolean; initialId?: string; loadError?: string }) {
  const router = useRouter()
  const [selected, setSelected] = useState(initialId || conversations[0]?.id || "")
  const [query, setQuery] = useState("")
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [uncertain, setUncertain] = useState<Record<string, boolean>>({})
  const [connectionOpen, setConnectionOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const pending = useRef<{ id: string; text: string; key: string } | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const needle = query.trim().toLowerCase()
  const visible = conversations.filter((item) => !needle || `${item.name} ${item.handle} ${item.excerpt}`.toLowerCase().includes(needle))
  const active = conversations.find((item) => item.id === selected) ?? visible[0]
  const activeId = active?.id
  const activeUnread = active?.unread ?? 0
  const draft = active ? drafts[active.id] ?? "" : ""

  useEffect(() => { const timer = setInterval(() => { if (document.visibilityState === "visible") router.refresh() }, 12000); return () => clearInterval(timer) }, [router])
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }) }, [activeId, active?.messages.length])
  useEffect(() => {
    if (!activeId || !activeUnread || document.visibilityState !== "visible") return
    const controller = new AbortController()
    void fetch(`/api/inbox/${encodeURIComponent(activeId)}/read`, { method: "POST", signal: controller.signal }).then((response) => { if (response.ok && !controller.signal.aborted) router.refresh() }).catch(() => {})
    return () => controller.abort()
  }, [activeId, activeUnread, router])

  async function action(kind: "messages" | "automation") {
    if (!active || busy || !canSend || (kind === "messages" && uncertain[active.id])) return
    const text = draft.trim()
    if (kind === "messages" && !text) return
    setBusy(true); setError(""); setNotice("")
    // The same idempotency key is reused while the same text is retried, so a retry cannot duplicate a send.
    if (kind === "messages" && (pending.current?.id !== active.id || pending.current?.text !== text)) pending.current = { id: active.id, text, key: crypto.randomUUID() }
    try {
      const response = await fetch(`/api/inbox/${encodeURIComponent(active.id)}/${kind}`, { method: kind === "messages" ? "POST" : "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(kind === "messages" ? { text, idempotency_key: pending.current!.key } : { enabled: !active.automationEnabled }), signal: AbortSignal.timeout(20000) })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível concluir a ação.")
      if (kind === "messages") {
        const outcome = sendOutcome(body)
        if (!outcome.accepted) {
          if (outcome.uncertain) setUncertain((current) => ({ ...current, [active.id]: true }))
          setError(outcome.message)
          router.refresh()
          return
        }
        setDrafts((current) => ({ ...current, [active.id]: "" }))
        pending.current = null
        setNotice(outcome.message)
      } else setNotice(active.automationEnabled ? "Você assumiu a conversa. A IA está pausada." : "IA retomada nesta conversa, dentro dos limites da operação.")
      router.refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Conexão interrompida. Confira o histórico antes de repetir.")
      if (kind === "messages" && (reason instanceof TypeError || (reason instanceof DOMException && ["TimeoutError", "AbortError"].includes(reason.name)))) setUncertain((current) => ({ ...current, [active.id]: true }))
    } finally { setBusy(false) }
  }

  const sidebar = (close: () => void): ReactNode => <div className="space-y-3">
    <div className="relative px-1">
      <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-sidebar-foreground/50" aria-hidden="true" />
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar conversa" aria-label="Buscar conversas" className="h-9 w-full rounded-lg bg-sidebar-foreground/5 pl-8 pr-2 text-sm outline-none placeholder:text-sidebar-foreground/45 focus-visible:ring-2 focus-visible:ring-sidebar-ring" />
    </div>
    {visible.length ? <ul className="space-y-0.5" aria-label="Conversas">{visible.map((item) => <li key={item.id}>
      <button type="button" aria-current={item.id === active?.id ? "true" : undefined} onClick={() => { setSelected(item.id); setError(""); setNotice(""); close() }}
        className={cn("flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-sidebar-foreground/5", item.id === active?.id && "bg-sidebar-foreground/10")}>
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-sidebar-foreground/10 text-[11px] font-semibold">{initials(item.name)}</span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2"><span className="truncate text-sm font-medium">{item.name}</span><span className="ml-auto shrink-0 text-[11px] text-sidebar-foreground/50">{item.time}</span></span>
          <span className="flex items-center gap-2"><span className="truncate text-xs text-sidebar-foreground/55">{item.excerpt}</span>{item.unread > 0 ? <span className="ml-auto grid min-w-5 shrink-0 place-items-center rounded-full bg-emerald-500 px-1.5 text-[10px] font-semibold text-white">{item.unread}</span> : null}</span>
        </span>
      </button>
    </li>)}</ul> : <p className="px-2 text-xs text-sidebar-foreground/50">{conversations.length ? "Nenhuma conversa com essa busca." : "As conversas do WhatsApp aparecem aqui."}</p>}
  </div>

  return <ImmersiveShell
    label="Conversas do WhatsApp"
    sidebar={sidebar}
    footer={<WhatsAppFooter onConnection={() => setConnectionOpen(true)} />}
    topBar={active ? <>
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-muted text-[11px] font-semibold">{initials(active.name)}</span>
      <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{active.name}</p><p className="truncate text-xs text-muted-foreground">{channelLabels[active.channel] ?? active.channel} · {active.handle}</p></div>
      <Button type="button" size="sm" variant="outline" disabled={busy || !canSend} onClick={() => void action("automation")}>{active.automationEnabled ? <Hand /> : <Bot />}<span className="hidden sm:inline">{active.automationEnabled ? "Assumir conversa" : "Retomar IA"}</span></Button>
      <Button type="button" variant="ghost" size="icon" aria-label="Detalhes do contato" onClick={() => setDetailsOpen(true)}><Info /></Button>
    </> : <><span className="font-medium">WhatsApp</span><Button type="button" variant="ghost" size="icon" className="ml-auto" aria-label="Atualizar" onClick={() => router.refresh()}><RefreshCw /></Button></>}
  >
    {loadError ? <p role="alert" className="m-4 rounded-lg border border-destructive/30 p-3 text-sm text-destructive">{loadError}</p> : null}
    {active ? <>
      <div className="min-h-0 flex-1 overflow-y-auto" role="log" aria-label={`Mensagens com ${active.name}`} aria-live="polite">
        <div className="mx-auto w-full max-w-3xl space-y-3 px-4 py-6">
          {active.messages.length ? active.messages.map((message) => <div key={message.id} className={cn("flex", message.from === "operator" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[80%] rounded-2xl px-3.5 py-2", message.from === "operator" ? "rounded-br-md bg-primary/15" : "rounded-bl-md bg-muted")}>
              <p className="whitespace-pre-wrap break-words text-[15px] leading-6">{message.text}</p>
              <p className="mt-1 text-right text-[11px] text-muted-foreground">{message.time}{message.from === "operator" && message.status ? ` · ${deliveryLabels[message.status] ?? message.status}` : ""}</p>
            </div>
          </div>) : <p className="py-16 text-center text-sm text-muted-foreground">Aguardando as mensagens desta conversa.</p>}
          <div ref={endRef} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-4">
        <p className="mb-2 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">{active.automationEnabled ? <><Bot className="size-3.5" aria-hidden="true" />A IA está respondendo esta conversa</> : <><Hand className="size-3.5" aria-hidden="true" />Atendimento humano · IA pausada</>}</p>
        <div className="rounded-3xl border bg-card px-3 pb-2 pt-3 shadow-sm focus-within:border-primary/40">
          <label htmlFor="wa-reply" className="sr-only">Resposta para {active.name}</label>
          <textarea id="wa-reply" rows={1} maxLength={4000} value={draft} disabled={!canSend || busy || uncertain[active.id]}
            placeholder={canSend ? "Escreva uma resposta" : "Seu perfil permite apenas leitura"}
            onChange={(event) => setDrafts((current) => ({ ...current, [active.id]: event.target.value }))}
            onInput={(event) => { const element = event.currentTarget; element.style.height = "auto"; element.style.height = `${Math.min(element.scrollHeight, 180)}px` }}
            onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void action("messages") } }}
            className="max-h-44 min-h-7 w-full resize-none bg-transparent px-1 text-[15px] leading-6 outline-none placeholder:text-muted-foreground disabled:opacity-60" />
          <div className="mt-1 flex items-center">
            <span className="px-1 text-[11px] text-muted-foreground">Ao responder, você assume a conversa.</span>
            <Button type="button" size="icon" className="ml-auto size-9 rounded-full" aria-label="Enviar resposta" disabled={busy || !canSend || uncertain[active.id] || !draft.trim()} onClick={() => void action("messages")}>{busy ? <LoaderCircle className="animate-spin" /> : <ArrowUp />}</Button>
          </div>
        </div>
        {error ? <p role="alert" className="mt-2 text-center text-sm text-destructive">{error}</p> : notice ? <p role="status" className="mt-2 text-center text-xs text-muted-foreground">{notice}</p> : null}
      </div>

      <Sheet open={detailsOpen} onOpenChange={setDetailsOpen}>
        <SheetContent side="right" className="w-[90vw] max-w-sm overflow-y-auto p-5">
          <SheetHeader className="p-0"><SheetTitle>{active.name}</SheetTitle><SheetDescription>{channelLabels[active.channel] ?? active.channel} · {active.handle}</SheetDescription></SheetHeader>
          <div className="space-y-5 text-sm">
            <div><p className="text-xs text-muted-foreground">Nível comercial</p><p className="mt-1 text-lg font-semibold">{temperatureLabels[active.temperature] ?? "Não classificado"} <span className="text-sm font-normal text-muted-foreground">{active.score}/100</span></p><p className="text-xs text-muted-foreground">{active.confidence}</p></div>
            <div><p className="font-medium">Próxima ação</p><p className="mt-1 text-muted-foreground">{active.nextAction}</p></div>
            <div><p className="font-medium">Sinais observados</p>{active.facts.length ? <ul className="mt-1 list-inside list-disc space-y-1 text-muted-foreground">{active.facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul> : <p className="mt-1 text-muted-foreground">Ainda não há sinais suficientes.</p>}</div>
            {active.consumerId ? <Button asChild variant="outline" className="w-full"><Link href={`/app/leads/${encodeURIComponent(active.consumerId)}`}>Abrir ficha do lead</Link></Button> : null}
          </div>
        </SheetContent>
      </Sheet>
    </> : <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <span className="mb-4 grid size-12 place-items-center rounded-full border bg-card text-emerald-400"><MessageCircle className="size-5" aria-hidden="true" /></span>
      <h1 className="text-2xl font-medium tracking-tight">Nenhuma conversa ainda</h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">Conecte o WhatsApp para que as conversas apareçam aqui e a Kiara possa ajudar no atendimento.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2"><Button type="button" onClick={() => setConnectionOpen(true)}><Cable />Conectar WhatsApp</Button><Button asChild variant="outline"><Link href="/app/whatsapp/automacao">Configurar automação</Link></Button></div>
    </div>}
    <ConnectionDialog open={connectionOpen} onOpenChange={setConnectionOpen} />
  </ImmersiveShell>
}

/** Same sidebar shell for secondary WhatsApp pages (automation settings). */
export function WhatsAppSectionShell({ title, children }: { title: string; children: ReactNode }) {
  const [connectionOpen, setConnectionOpen] = useState(false)
  return <ImmersiveShell
    label="WhatsApp"
    sidebar={(close) => <Link href="/app/whatsapp" onClick={close} className={footerLink}><ArrowLeft className="size-4" aria-hidden="true" />Conversas</Link>}
    footer={<WhatsAppFooter onConnection={() => setConnectionOpen(true)} />}
    topBar={<span className="truncate font-medium">{title}</span>}
  >
    <div className="min-h-0 flex-1 overflow-y-auto"><div className="mx-auto w-full max-w-4xl p-4 sm:p-6">{children}</div></div>
    <ConnectionDialog open={connectionOpen} onOpenChange={setConnectionOpen} />
  </ImmersiveShell>
}
