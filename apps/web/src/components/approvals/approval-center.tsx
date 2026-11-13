"use client"

import Link from "next/link"
import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"
import { Bell, CalendarPlus, Check, CheckCheck, Copy, ExternalLink, Globe, LoaderCircle, Mail, Megaphone, MessageCircle, Monitor, RefreshCw, Send, ShieldCheck, X, type LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { burst } from "@/components/fx/fx"
import { cn } from "@/lib/utils"

export type ActionRequest = {
  id: string
  kind: string
  title: string
  payload: Record<string, string | number>
  status: "pending" | "approved" | "rejected" | "done" | "failed"
  note: string | null
  version: number
  flow_name: string | null
  created_at: string
  decided_at: string | null
}

const kinds: Record<string, { label: string; icon: LucideIcon; color: string }> = {
  whatsapp: { label: "WhatsApp", icon: MessageCircle, color: "#34d399" },
  email: { label: "E-mail", icon: Mail, color: "#38bdf8" },
  calendar: { label: "Agenda", icon: CalendarPlus, color: "#fb923c" },
  notice: { label: "Aviso da Kiara", icon: Bell, color: "#a78bfa" },
  "web.browse": { label: "Navegar em site", icon: Globe, color: "#22d3ee" },
  "machine.command": { label: "Computador", icon: Monitor, color: "#f472b6" },
  "machine.files": { label: "Arquivos", icon: Monitor, color: "#f472b6" },
  social: { label: "Rede social", icon: Send, color: "#e879f9" },
  ads: { label: "Anúncio", icon: Megaphone, color: "#facc15" },
}
const statusLabels: Record<ActionRequest["status"], string> = { pending: "Aguardando você", approved: "Aprovado", rejected: "Recusado", done: "Feito", failed: "Falhou" }
// The field a person usually reviews and edits before approving.
const editableFields = ["text", "body", "caption"]
const fieldLabels: Record<string, string> = {
  to: "Para", subject: "Assunto", title: "Título", when: "Quando", minutes: "Duração (min)", url: "Site", steps: "O que fazer",
  action: "Ação", folder: "Pasta", rule: "Regra", media: "Mídia", objective: "Objetivo", daily: "Por dia", days: "Dias", keywords: "Palavras-chave",
}
const objectiveLabels: Record<string, string> = { traffic: "Tráfego para o site", leads: "Geração de leads", messages: "Mensagens no WhatsApp", awareness: "Reconhecimento" }
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })

function displayValue(key: string, value: string | number) {
  if (key === "objective") return objectiveLabels[String(value)] ?? String(value)
  if (key === "daily" && Number.isFinite(Number(value))) return brl.format(Number(value))
  return String(value)
}
const when = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" })

function kindInfo(kind: string) {
  return kinds[kind] ?? kinds[kind.split(".")[0]] ?? { label: "Ação", icon: ShieldCheck, color: "#94a3b8" }
}

/** wa.me link for Brazilian numbers typed with or without country code. */
export function whatsappLink(to: unknown, text: string): string | null {
  let digits = String(to ?? "").replace(/\D/g, "")
  if (digits.length === 10 || digits.length === 11) digits = `55${digits}`
  if (!/^[1-9]\d{11,13}$/.test(digits)) return null
  return `https://wa.me/${digits}?text=${encodeURIComponent(text.slice(0, 3000))}`
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...init?.headers } })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = payload && typeof payload === "object" ? (payload as { error?: { message?: unknown } }).error : null
    throw new Error(typeof error?.message === "string" ? error.message : `Não foi possível concluir (HTTP ${response.status}).`)
  }
  return payload as T
}

const SWIPE_DISTANCE = 110

function RequestCard({ item, onChange, swipeable = false }: { item: ActionRequest; onChange: (next: ActionRequest) => void; swipeable?: boolean }) {
  const cardRef = useRef<HTMLElement>(null)
  const dragRef = useRef<{ x: number } | null>(null)
  const [dx, setDx] = useState(0)
  const [leaving, setLeaving] = useState<-1 | 0 | 1>(0)
  const [dragging, setDragging] = useState(false)
  const info = kindInfo(item.kind)
  const Icon = info.icon
  const field = editableFields.find((key) => typeof item.payload[key] === "string")
  const [draft, setDraft] = useState(field ? String(item.payload[field]) : "")
  const [busy, setBusy] = useState("")
  const [error, setError] = useState("")
  const [copied, setCopied] = useState(false)
  const notice = item.kind === "notice"
  const text = notice ? String(item.payload.text ?? "") : draft
  const wa = item.kind === "whatsapp" ? whatsappLink(item.payload.to, draft) : null
  const details = Object.entries(item.payload).filter(([key, value]) => key !== "entrada" && key !== field && !(notice && key === "text") && String(value).trim())

  async function decide(decision: "approve" | "reject" | "done") {
    setBusy(decision); setError("")
    try {
      const payload = field && draft !== item.payload[field] ? { [field]: draft } : undefined
      const next = await call<ActionRequest>(`/api/approvals/${encodeURIComponent(item.id)}/decision`, { method: "POST", body: JSON.stringify({ decision, version: item.version, payload }) })
      if (decision !== "reject") burst(cardRef.current, "#34d399", 22)
      onChange(next)
    } catch (cause) {
      setLeaving(0); setDx(0)
      setError(cause instanceof Error ? cause.message : "Não foi possível registrar a decisão.")
    } finally { setBusy("") }
  }

  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1800) } catch { setError("O navegador bloqueou a cópia.") }
  }

  // Swipe like a card deck: right approves, left rejects (notices can only be acknowledged).
  const canSwipe = swipeable && item.status === "pending" && !busy
  function grab(event: ReactPointerEvent<HTMLElement>) {
    if (!canSwipe || event.button !== 0 || (event.target as Element).closest("textarea, input, select, button, a, label, dl")) return
    dragRef.current = { x: event.clientX }
    setDragging(true)
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  function drag(event: ReactPointerEvent<HTMLElement>) {
    if (dragRef.current) setDx(event.clientX - dragRef.current.x)
  }
  function release() {
    if (!dragRef.current) return
    dragRef.current = null
    setDragging(false)
    if (dx > SWIPE_DISTANCE) { setLeaving(1); void decide("approve") }
    else if (dx < -SWIPE_DISTANCE && !notice) { setLeaving(-1); void decide("reject") }
    else setDx(0)
  }
  const offset = leaving ? leaving * 900 : dx
  const swipeStyle = swipeable ? {
    transform: `translateX(${offset}px) rotate(${offset / 22}deg)`,
    transition: dragging ? "none" : "transform .45s cubic-bezier(.2,.8,.2,1), opacity .45s",
    opacity: leaving ? 0 : 1, touchAction: "pan-y" as const,
  } : undefined
  const approveHint = Math.max(0, Math.min(1, dx / SWIPE_DISTANCE)), rejectHint = notice ? 0 : Math.max(0, Math.min(1, -dx / SWIPE_DISTANCE))

  return <article ref={cardRef} style={swipeStyle} onPointerDown={grab} onPointerMove={drag} onPointerUp={release} onPointerCancel={release}
    className={cn("relative rounded-2xl border bg-card/80 p-4 shadow-sm backdrop-blur-xl sm:p-5", canSwipe && "cursor-grab active:cursor-grabbing")}>
    {swipeable ? <>
      <span aria-hidden="true" style={{ opacity: approveHint }} className="pointer-events-none absolute left-1/2 top-6 z-10 -translate-x-1/2 rotate-[-10deg] rounded-lg border-2 border-emerald-400 bg-card/90 px-3 py-1 text-sm font-bold tracking-widest text-emerald-400">{notice ? "VISTO" : "APROVAR"}</span>
      <span aria-hidden="true" style={{ opacity: rejectHint }} className="pointer-events-none absolute left-1/2 top-6 z-10 -translate-x-1/2 rotate-[10deg] rounded-lg border-2 border-rose-400 bg-card/90 px-3 py-1 text-sm font-bold tracking-widest text-rose-400">RECUSAR</span>
    </> : null}
    <header className="flex items-start gap-3">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl" style={{ background: `color-mix(in oklab, ${info.color} 18%, transparent)`, color: info.color }}><Icon className="size-5" aria-hidden="true" /></span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{info.label}{item.flow_name ? ` · ${item.flow_name}` : ""}</p>
        <h2 className="mt-0.5 break-words font-semibold">{item.title}</h2>
        <p className="text-xs text-muted-foreground">{when.format(new Date(item.created_at))}</p>
      </div>
      {item.status !== "pending" ? <span className={cn("shrink-0 rounded-full px-2.5 py-1 text-xs font-medium", item.status === "rejected" || item.status === "failed" ? "bg-destructive/15 text-destructive" : item.status === "approved" ? "bg-sky-400/15 text-sky-300" : "bg-emerald-400/15 text-emerald-300")}>{statusLabels[item.status]}</span> : null}
    </header>

    {details.length ? <dl className="mt-3 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">{details.map(([key, value]) => <div key={key} className="min-w-0"><dt className="text-xs text-muted-foreground">{fieldLabels[key] ?? key}</dt><dd className="whitespace-pre-wrap break-words">{displayValue(key, value)}</dd></div>)}</dl> : null}

    {notice ? <p className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-muted/40 p-3 text-sm">{text || "Sem conteúdo."}</p>
      : field ? item.status === "pending"
        ? <div className="mt-3 space-y-1.5"><label htmlFor={`draft-${item.id}`} className="text-xs text-muted-foreground">Texto (você pode ajustar antes de aprovar)</label><Textarea id={`draft-${item.id}`} value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-28" /></div>
        : <p className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-muted/40 p-3 text-sm">{draft}</p>
        : null}

    {item.status === "approved" ? <p className="mt-3 rounded-xl bg-sky-400/10 px-3 py-2 text-xs text-sky-200">Aprovado. A Kiara executa assim que esta conexão estiver ativa no servidor. Se preferir, faça agora pelo botão abaixo e marque como feito.</p> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-destructive">{error}</p> : null}

    <footer className="mt-4 flex flex-wrap gap-2">
      {item.status === "pending" && notice ? <Button type="button" size="sm" disabled={Boolean(busy)} onClick={() => void decide("approve")}>{busy ? <LoaderCircle className="animate-spin" /> : <Check />}Ok, visto</Button> : null}
      {item.status === "pending" && !notice ? <>
        <Button type="button" size="sm" disabled={Boolean(busy)} onClick={() => void decide("approve")}>{busy === "approve" ? <LoaderCircle className="animate-spin" /> : <Check />}Aprovar</Button>
        <Button type="button" size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => void decide("reject")}>{busy === "reject" ? <LoaderCircle className="animate-spin" /> : <X />}Recusar</Button>
      </> : null}
      {(item.status === "pending" || item.status === "approved") && !notice ? <>
        {wa ? <Button asChild size="sm" variant="outline"><a href={wa} target="_blank" rel="noreferrer"><ExternalLink />Abrir no WhatsApp</a></Button> : null}
        {text ? <Button type="button" size="sm" variant="ghost" onClick={() => void copy()}>{copied ? <Check /> : <Copy />}{copied ? "Copiado" : "Copiar texto"}</Button> : null}
        <Button type="button" size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => void decide("done")}>{busy === "done" ? <LoaderCircle className="animate-spin" /> : <CheckCheck />}Já fiz, marcar como feito</Button>
      </> : null}
    </footer>
  </article>
}

/** Pending requests as a card deck (top card swipeable); approved ones waiting for execution listed below. */
function PendingDeck({ items, onChange }: { items: ActionRequest[]; onChange: (next: ActionRequest) => void }) {
  const deck = items.filter((item) => item.status === "pending")
  const rest = items.filter((item) => item.status !== "pending")
  const [top, ...behind] = deck
  return <>
    {top ? <div className="fx-rise">
      <p className="mb-2 text-xs text-muted-foreground">{deck.length > 1 ? `1 de ${deck.length} · ` : ""}Arraste para a direita para aprovar, para a esquerda para recusar, ou use os botões.</p>
      <RequestCard key={`${top.id}-${top.version}`} item={top} onChange={onChange} swipeable />
      {behind.slice(0, 2).map((item, index) => <div key={item.id} aria-hidden="true" className="mx-auto h-3 rounded-b-2xl border border-t-0 bg-card/50" style={{ width: `${94 - index * 6}%`, opacity: .8 - index * .3 }} />)}
    </div> : null}
    {rest.length ? <div className="space-y-3 pt-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Aprovados, aguardando execução</p>
      {rest.map((item, index) => <div key={`${item.id}-${item.version}`} className="fx-rise" style={{ "--i": index } as React.CSSProperties}><RequestCard item={item} onChange={onChange} /></div>)}
    </div> : null}
  </>
}

/** `preview` renders fixed items without calling the API (UI verification only). */
export function ApprovalCenter({ preview }: { preview?: ActionRequest[] } = {}) {
  const [tab, setTab] = useState<"pending" | "history">("pending")
  const [items, setItems] = useState<ActionRequest[]>(preview ?? [])
  const [pending, setPending] = useState(preview?.length ?? 0)
  const [loading, setLoading] = useState(!preview)
  const [error, setError] = useState("")

  const load = useCallback(async (next: "pending" | "history") => {
    setLoading(true); setError("")
    try {
      const data = await call<{ items: ActionRequest[]; pending: number }>(`/api/approvals?status=${next}`)
      setItems(data.items); setPending(data.pending)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível carregar a Central.")
    } finally { setLoading(false) }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- loads the selected tab from the API
  useEffect(() => { if (!preview) void load(tab) }, [load, tab, preview])

  function changed(next: ActionRequest) {
    setItems((current) => tab === "pending" && next.status !== "pending" && next.status !== "approved" ? current.filter((item) => item.id !== next.id) : current.map((item) => item.id === next.id ? next : item))
    if (next.status !== "pending") setPending((count) => Math.max(0, count - (items.find((item) => item.id === next.id)?.status === "pending" ? 1 : 0)))
  }

  return <main className="mx-auto w-full max-w-3xl">
    <header className="flex flex-wrap items-end gap-4">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.2em] text-primary"><ShieldCheck className="size-4" aria-hidden="true" />Você aprova. A Kiara executa.</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Central de aprovações</h1>
        <p className="mt-1 text-sm text-muted-foreground">Mensagens, posts, anúncios e tarefas que a Kiara preparou. Nada sai sem a sua decisão.</p>
      </div>
      <Button type="button" variant="outline" size="sm" onClick={() => void load(tab)} disabled={loading}><RefreshCw className={cn(loading && "animate-spin")} />Atualizar</Button>
    </header>

    <div role="tablist" aria-label="Filtro" className="mt-6 inline-flex rounded-xl border bg-card/60 p-1">
      {(["pending", "history"] as const).map((value) => <button key={value} type="button" role="tab" aria-selected={tab === value} onClick={() => setTab(value)}
        className={cn("inline-flex min-h-9 items-center gap-2 rounded-lg px-4 text-sm font-medium transition", tab === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
        {value === "pending" ? "Pendentes" : "Histórico"}
        {value === "pending" && pending ? <span className={cn("rounded-full px-1.5 text-xs tabular-nums", tab === value ? "bg-primary-foreground/20" : "bg-primary/20 text-primary")}>{pending}</span> : null}
      </button>)}
    </div>

    <section className="mt-5 space-y-3" aria-live="polite">
      {error ? <p role="alert" className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">{error}</p>
        : loading && !items.length ? <p className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Carregando…</p>
          : items.length ? tab === "pending" ? <PendingDeck items={items} onChange={changed} />
            : items.map((item, index) => <div key={`${item.id}-${item.version}`} className="fx-rise" style={{ "--i": index } as React.CSSProperties}><RequestCard item={item} onChange={changed} /></div>)
            : <div className="rounded-2xl border border-dashed p-10 text-center">
              <CheckCheck className="mx-auto size-8 text-emerald-400" aria-hidden="true" />
              <p className="mt-3 font-medium">{tab === "pending" ? "Tudo em dia." : "Nenhuma decisão ainda."}</p>
              <p className="mt-1 text-sm text-muted-foreground">{tab === "pending" ? "Quando uma automação preparar uma mensagem, post ou anúncio, ele aparece aqui." : "As ações aprovadas, recusadas e feitas aparecem aqui."}</p>
              {tab === "pending" ? <Link href="/app/automation" className="mt-4 inline-block text-sm text-primary hover:underline">Criar uma automação</Link> : null}
            </div>}
    </section>
  </main>
}
