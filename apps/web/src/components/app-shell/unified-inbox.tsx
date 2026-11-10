"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Bot, Hand, Loader2, MessageCircle, RefreshCw, Search, Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { channelLabels, temperatureLabels, deliveryLabels, sendOutcome, type InboxConversationDTO } from "@/lib/api/inbox-contract"
import { cn } from "@/lib/utils"

export function UnifiedInbox({ conversations, initialId = "", canSend = false }: { conversations: readonly InboxConversationDTO[]; initialId?: string; canSend?: boolean }) {
  const router = useRouter()
  const [selected, setSelected] = useState(initialId || conversations[0]?.id || "")
  const [query, setQuery] = useState("")
  const [channel, setChannel] = useState("all")
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [uncertain, setUncertain] = useState<Record<string, boolean>>({})
  const pending = useRef<{ id: string; text: string; key: string } | null>(null)
  const visible = conversations.filter(item => (channel === "all" || item.channel === channel) && `${item.name} ${item.handle} ${item.excerpt}`.toLowerCase().includes(query.toLowerCase()))
  const active = visible.find(item => item.id === selected) ?? visible[0]
  const channels = [...new Set(conversations.map(item => item.channel))]
  useEffect(() => { const timer = setInterval(() => { if (document.visibilityState === "visible") router.refresh() }, 12000); return () => clearInterval(timer) }, [router])
  const activeId = active?.id
  const activeUnread = active?.unread ?? 0
  useEffect(() => {
    if (!activeId || !activeUnread || document.visibilityState !== "visible") return
    const controller = new AbortController()
    void fetch(`/api/inbox/${encodeURIComponent(activeId)}/read`, { method: "POST", signal: controller.signal }).then(response => { if (response.ok && !controller.signal.aborted) router.refresh() }).catch(() => {})
    return () => controller.abort()
  }, [activeId, activeUnread, router])

  async function action(kind: "messages" | "automation") {
    if (!active || busy || !canSend || (kind === "messages" && uncertain[active.id])) return
    const text = (drafts[active.id] ?? "").trim()
    if (kind === "messages" && !text) return
    setBusy(true); setError(""); setNotice("")
    if (kind === "messages" && (pending.current?.id !== active.id || pending.current?.text !== text)) pending.current = { id: active.id, text, key: crypto.randomUUID() }
    try {
      const response = await fetch(`/api/inbox/${encodeURIComponent(active.id)}/${kind}`, { method: kind === "messages" ? "POST" : "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(kind === "messages" ? { text, idempotency_key: pending.current!.key } : { enabled: !active.automationEnabled }), signal: AbortSignal.timeout(20000) })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.error?.message || "Não foi possível concluir a ação.")
      if (kind === "messages") {
        const outcome = sendOutcome(body)
        if (!outcome.accepted) {
          if (outcome.uncertain) setUncertain(current => ({ ...current, [active.id]: true }))
          setError(outcome.message)
          router.refresh()
          return
        }
        setDrafts(current => ({ ...current, [active.id]: "" }))
        pending.current = null
        setNotice(outcome.message)
      } else setNotice(active.automationEnabled ? "Você assumiu esta conversa. A IA está pausada." : "Retomada solicitada. A política e os limites da operação continuam valendo.")
      router.refresh()
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Conexão interrompida. Confira o histórico antes de repetir."); if (kind === "messages" && (reason instanceof TypeError || (reason instanceof DOMException && ["TimeoutError", "AbortError"].includes(reason.name)))) setUncertain(current => ({ ...current, [active.id]: true })) }
    finally { setBusy(false) }
  }

  return <section className="overflow-hidden rounded-2xl border bg-card shadow-sm" aria-label="Caixa de entrada multicanal">
    <header className="flex flex-wrap items-center gap-3 border-b p-4"><div className="relative min-w-48 flex-1"><Search aria-hidden className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input aria-label="Buscar conversas" placeholder="Nome, telefone ou mensagem" className="pl-9" value={query} onChange={event => setQuery(event.target.value)} /></div><select aria-label="Filtrar canal" className="h-10 rounded-md border bg-background px-3 text-sm" value={channel} onChange={event => setChannel(event.target.value)}><option value="all">Todos os canais</option>{channels.map(value => <option key={value} value={value}>{channelLabels[value] ?? value}</option>)}</select><Button variant="outline" onClick={() => router.refresh()}><RefreshCw aria-hidden />Atualizar</Button></header>
    <div className="grid min-h-[640px] lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_270px]">
      <aside className="max-h-72 overflow-y-auto border-b lg:max-h-[760px] lg:border-b-0 lg:border-r" aria-label="Conversas"><p className="px-4 py-3 text-xs text-muted-foreground">{visible.length} conversas · atualização automática</p>{visible.length ? visible.map(item => <button key={item.id} className={cn("w-full border-b p-4 text-left hover:bg-muted/50", item.id === active?.id && "bg-primary/5 ring-1 ring-inset ring-primary/20")} onClick={() => { setSelected(item.id); setError(""); setNotice("") }} aria-pressed={item.id === active?.id}><div className="flex items-center justify-between gap-2"><strong className="truncate text-sm">{item.name}</strong><time className="text-xs text-muted-foreground">{item.time}</time></div><p className="mt-1 text-xs text-primary">{channelLabels[item.channel] ?? item.channel} · {temperatureLabels[item.temperature] ?? "Não classificado"}</p><p className="mt-2 truncate text-xs text-muted-foreground">{item.excerpt}</p>{item.unread > 0 && <Badge className="mt-2">{item.unread} não lidas</Badge>}</button>) : <p className="p-6 text-sm text-muted-foreground">Nenhuma conversa neste filtro.</p>}</aside>
      {active ? <main className="flex min-w-0 flex-col"><header className="flex flex-wrap items-center gap-3 border-b p-4"><MessageCircle aria-hidden className="size-5 text-primary" /><div className="min-w-0 flex-1"><h2 className="truncate font-semibold">{active.name}</h2><p className="text-xs text-muted-foreground">{channelLabels[active.channel] ?? active.channel} · {active.handle}</p></div><Button variant="outline" disabled={busy || !canSend} onClick={() => void action("automation")}>{active.automationEnabled ? <Hand aria-hidden /> : <Bot aria-hidden />}{active.automationEnabled ? "Assumir conversa" : "Retomar IA"}</Button></header><div className="flex max-h-[520px] min-h-72 flex-1 flex-col gap-4 overflow-y-auto bg-muted/20 p-4">{active.messages.length ? active.messages.map(message => <article key={message.id} className={cn("max-w-[88%] rounded-2xl border bg-background p-3", message.from === "operator" && "ml-auto bg-primary/5")}><p className="mb-1 text-[10px] font-semibold text-muted-foreground">{message.from === "lead" ? active.name : "Equipe / Kiara"}</p><p className="whitespace-pre-wrap break-words text-sm">{message.text}</p><p className="mt-2 text-right text-[10px] text-muted-foreground">{message.time}{message.status ? ` · ${deliveryLabels[message.status] ?? message.status}` : ""}</p></article>) : <p className="m-auto text-sm text-muted-foreground">Aguardando mensagens sincronizadas.</p>}</div><footer className="space-y-3 border-t p-4">{!canSend && <p className="text-xs text-muted-foreground">Seu perfil permite leitura. Um administrador pode enviar respostas e controlar o agente.</p>}<div className="flex items-center justify-between text-xs"><span>{active.automationEnabled ? "IA habilitada nesta conversa" : "Atendimento humano / IA pausada"}</span><Link href="/app/followups" className="text-primary underline">Configurar operação</Link></div>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm text-primary">{notice}</p>}<Textarea aria-label={`Resposta para ${active.name}`} maxLength={4000} disabled={!canSend || uncertain[active.id]} value={drafts[active.id] ?? ""} onChange={event => setDrafts(current => ({ ...current, [active.id]: event.target.value }))} placeholder="Escreva a resposta. O envio usa o canal desta conversa." /><Button className="w-full sm:w-auto" disabled={busy || !canSend || uncertain[active.id] || !(drafts[active.id] ?? "").trim()} onClick={() => void action("messages")}>{busy ? <Loader2 aria-hidden className="animate-spin" /> : <Send aria-hidden />}Enviar resposta</Button><p className="text-xs text-muted-foreground">Ao responder, você assume a conversa. Em resultado incerto, confira o histórico antes de repetir.</p></footer></main> : <div className="grid place-items-center p-8 text-center"><div><MessageCircle aria-hidden className="mx-auto mb-3 size-8 text-primary" /><h2 className="font-semibold">Sua central de atendimento</h2><p className="mt-2 max-w-md text-sm text-muted-foreground">Mensagens dos canais conectados aparecerão aqui. Conecte o executor WhatsApp ou configure os canais em Integrações.</p><Button asChild className="mt-4"><Link href="/app/followups">Conectar WhatsApp</Link></Button></div></div>}
      {active && <aside className="space-y-5 border-t p-5 xl:border-l xl:border-t-0"><div><p className="text-xs text-muted-foreground">Nível comercial</p><p className="mt-1 text-xl font-semibold">{temperatureLabels[active.temperature] ?? "Não classificado"} <span className="text-sm text-muted-foreground">{active.score}/100</span></p></div><div><h3 className="text-sm font-semibold">Próxima ação</h3><p className="mt-2 text-sm text-muted-foreground">{active.nextAction}</p></div><div><h3 className="text-sm font-semibold">Sinais observados</h3>{active.facts.length ? <ul className="mt-2 list-inside list-disc space-y-2 text-xs text-muted-foreground">{active.facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul> : <p className="mt-2 text-xs text-muted-foreground">Ainda não há sinais suficientes.</p>}</div><p className="text-xs text-muted-foreground">{active.confidence}</p>{active.consumerId && <Button asChild variant="outline"><Link href={`/app/leads/${encodeURIComponent(active.consumerId)}`}>Abrir ficha do lead</Link></Button>}</aside>}
    </div>
  </section>
}
