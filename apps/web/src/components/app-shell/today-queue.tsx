"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { ArrowRight, Check, Clock3, Copy, Flame, Loader2, MapPin, MessageCircle, Phone, RotateCcw, SkipForward, Sparkles, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { growth, whatsappLink } from "@/lib/api/growth"
import { leadDisplayName, type PipelineEntry } from "@/lib/api/pipeline"
import { salesRequest, type SalesProfile } from "@/lib/api/sales"
import { cn } from "@/lib/utils"

type Kind = "first_contact" | "follow_up" | "reactivation"
type Item = { entry: PipelineEntry; kind: Kind; reason: string; order: number }
const KIND_LABEL: Record<Kind, string> = { first_contact: "Primeiro contato", follow_up: "Acompanhamento", reactivation: "Negociação parada" }
const ADJUSTMENTS = ["Mais curta", "Mais formal", "Mais descontraída", "Mencione um benefício concreto"]
const DAY = 86_400_000

/** Today's work, in order: follow-ups that are due, stalled negotiations, then new leads (best first). */
export function buildQueue(entries: PipelineEntry[], now: number): Item[] {
  const items: Item[] = []
  for (const entry of entries) {
    const sent = (entry.activities ?? []).filter((activity) => activity.status === "sent")
    const replied = (entry.activities ?? []).some((activity) => activity.status === "replied")
    const due = entry.next_action_at ? new Date(entry.next_action_at).getTime() : 0
    const idle = Math.floor((now - new Date(entry.updated_at).getTime()) / DAY)
    if (entry.stage === "new" && !sent.length) items.push({ entry, kind: "first_contact", reason: "Ainda não recebeu nenhuma mensagem", order: 2_000 - (entry.consumer.fit?.score ?? 0) })
    else if (entry.stage === "contacted" && !replied && sent.length && sent.length < 4 && due && due <= now + DAY / 2)
      items.push({ entry, kind: "follow_up", reason: `Sem resposta desde a ${sent.length}ª mensagem`, order: due / DAY - 1_000_000 })
    else if ((entry.stage === "qualified" || entry.stage === "opportunity") && idle >= 7)
      items.push({ entry, kind: "reactivation", reason: `Sem novidade há ${idle} dias`, order: -idle })
  }
  return items.sort((a, b) => a.order - b.order)
}

export function TodayQueue({ entries }: { entries: PipelineEntry[] }) {
  const [now] = useState(() => Date.now())
  const queue = useMemo(() => buildQueue(entries, now), [entries, now])
  const [done, setDone] = useState<Set<string>>(new Set())
  const [index, setIndex] = useState(0)
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [message, setMessage] = useState("")
  const [writing, setWriting] = useState(false)
  const [opened, setOpened] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const pending = queue.filter((item) => !done.has(item.entry.id))
  const current = pending[Math.min(index, Math.max(0, pending.length - 1))]

  useEffect(() => { salesRequest<SalesProfile>("/api/sales/profile").then(setProfile).catch(() => undefined) }, [])
  useEffect(() => {
    if (!current) return
    const consumer = current.entry.consumer
    const template = profile?.templates[current.kind === "first_contact" ? (consumer.website_status === "not_listed" ? "no_website" : "first_contact") : current.kind === "follow_up" ? "follow_up" : "reactivation"]
      || profile?.templates.first_contact || "Olá, {nome}! Tudo bem? Aqui é {remetente}. Posso te mostrar uma ideia rápida para {nicho}?"
    const values: Record<string, string> = { remetente: profile?.sender_name || profile?.business_name || "[seu nome]", nome: leadDisplayName(consumer),
      nicho: consumer.research_query || "o seu negócio", cidade: consumer.address?.split(" - ").at(-1) || "sua região", oferta: profile?.offer || "" }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessage(template.replace(/\{(remetente|nome|nicho|cidade|oferta)\}/g, (_, key: string) => values[key])); setOpened(false); setError("")
  }, [current, profile])

  async function write(note = "") {
    if (!current) return
    setWriting(true); setError("")
    try {
      const reply = await growth<{ message: string }>("sales/draft", { method: "POST", body: JSON.stringify({ pipeline_entry_id: current.entry.id, kind: current.kind, note }) })
      setMessage(reply.message)
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível escrever agora.") }
    finally { setWriting(false) }
  }

  async function record(status: "opened" | "sent") {
    if (!current) return
    await salesRequest("/api/sales/activities", { method: "POST", body: JSON.stringify({ pipeline_entry_id: current.entry.id, channel: "whatsapp", status, body: message, follow_up_hours: status === "sent" ? profile?.follow_up_hours ?? 48 : null }) })
  }

  async function markSent() {
    if (!current) return
    setSaving(true); setError("")
    try { await record("sent"); setDone((value) => new Set(value).add(current.entry.id)) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível registrar.") }
    finally { setSaving(false) }
  }

  if (!queue.length) return <div className="kiara-soft-panel rounded-2xl border p-10 text-center">
    <Check className="mx-auto mb-3 size-8 text-emerald-400" aria-hidden="true" />
    <p className="text-lg font-medium">Nada pendente por hoje</p>
    <p className="mt-1 text-sm text-muted-foreground">Os acompanhamentos aparecem aqui no dia certo. Que tal buscar novos leads?</p>
    <Button asChild className="mt-5"><Link href="/app/hunter">Buscar leads<ArrowRight /></Link></Button>
  </div>
  if (!current) return <div className="kiara-soft-panel rounded-2xl border p-10 text-center">
    <Sparkles className="mx-auto mb-3 size-8 text-primary" aria-hidden="true" />
    <p className="text-lg font-medium">Fila concluída! {done.size} {done.size === 1 ? "mensagem enviada" : "mensagens enviadas"} hoje.</p>
    <p className="mt-1 text-sm text-muted-foreground">A Kiara lembra você dos acompanhamentos nos próximos dias.</p>
  </div>

  const consumer = current.entry.consumer
  const link = whatsappLink(message, consumer.whatsapp_url, consumer.phone)
  const facts = [consumer.website_status === "not_listed" ? "Sem site" : null, consumer.rating ? `Nota ${consumer.rating.toFixed(1).replace(".", ",")} (${consumer.user_rating_count ?? 0})` : null,
    ...(consumer.fit?.reasons.slice(0, 3).map((reason) => reason.text) ?? [])].filter(Boolean) as string[]

  return <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-6">
    <aside aria-label="Fila de hoje" className="kiara-soft-panel -mx-1 h-fit rounded-2xl border p-2 lg:mx-0 lg:p-3">
      <p className="px-2 pb-2 text-sm font-medium">{pending.length} pendente{pending.length === 1 ? "" : "s"} · {done.size} feito{done.size === 1 ? "" : "s"}</p>
      <ol className="flex snap-x gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] lg:block lg:max-h-[60vh] lg:space-y-1 lg:overflow-y-auto lg:pb-0">{pending.map((item, position) => <li key={item.entry.id} className="w-[11.5rem] shrink-0 snap-start lg:w-auto">
        <button type="button" onClick={() => setIndex(position)} aria-current={item === current ? "true" : undefined}
          className={cn("w-full rounded-lg border border-transparent px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted/50", item === current && "border-primary/40 bg-primary/15 shadow-[0_0_18px_-6px_rgb(124_77_255/.7)]")}>
          <span className="block truncate font-medium">{leadDisplayName(item.entry.consumer)}</span>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">{item.kind === "first_contact" ? <Sparkles className="size-3" /> : item.kind === "follow_up" ? <Clock3 className="size-3" /> : <Flame className="size-3" />}{KIND_LABEL[item.kind]}</span>
        </button>
      </li>)}</ol>
    </aside>

    <section aria-labelledby="queue-lead" className="kiara-soft-panel space-y-5 rounded-2xl border p-5 sm:p-6 fx-rise" key={current.entry.id}>
      <header className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[.16em] text-primary">{KIND_LABEL[current.kind]} · {current.reason}</p>
        <h2 id="queue-lead" className="text-2xl font-medium tracking-tight"><Link href={`/app/leads/${encodeURIComponent(consumer.id)}`} className="hover:underline">{leadDisplayName(consumer)}</Link></h2>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {consumer.address ? <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" aria-hidden="true" />{consumer.address}</span> : null}
          {consumer.phone ? <a href={`tel:${consumer.phone.replace(/[^\d+]/g, "")}`} className="inline-flex items-center gap-1 hover:text-foreground"><Phone className="size-3.5" aria-hidden="true" />{consumer.phone}</a> : null}
          {consumer.rating ? <span className="inline-flex items-center gap-1"><Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden="true" />{consumer.rating.toFixed(1).replace(".", ",")}</span> : null}
        </div>
        {facts.length ? <ul className="flex flex-wrap gap-1.5">{facts.map((fact) => <li key={fact} className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[11px] text-emerald-300">{fact}</li>)}</ul> : null}
      </header>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="queue-message" className="text-sm font-medium">Mensagem</label>
          <Button type="button" size="sm" className="ml-auto" onClick={() => void write()} disabled={writing}>{writing ? <Loader2 className="animate-spin" /> : <Sparkles />}{writing ? "Escrevendo…" : "Escrever com a Kiara"}</Button>
        </div>
        <textarea id="queue-message" value={message} onChange={(event) => setMessage(event.target.value)} rows={6} className="w-full resize-y rounded-xl border bg-background p-3 text-[15px] leading-6 outline-none focus:border-primary/50" />
        <div className="flex flex-wrap gap-1.5">{ADJUSTMENTS.map((note) => <button key={note} type="button" disabled={writing} onClick={() => void write(note)} className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground disabled:opacity-50"><RotateCcw className="mr-1 inline size-3" aria-hidden="true" />{note}</button>)}</div>
        <p className="text-xs text-muted-foreground">{message.length} caracteres · a mensagem sai do seu WhatsApp, sem risco para o número.</p>
      </div>

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      <div className="kiara-mobile-sticky flex items-center gap-2 border-t pt-4">
        {link ? <Button asChild size="lg" className="flex-1 bg-emerald-500 text-white shadow-[0_10px_30px_-10px_rgb(16_185_129/.8)] hover:bg-emerald-600 sm:flex-none"><a href={link} target="_blank" rel="noopener noreferrer" onClick={() => { setOpened(true); void record("opened").catch(() => undefined) }}><MessageCircle />Abrir no WhatsApp</a></Button>
          : <Button type="button" size="lg" variant="outline" className="flex-1 sm:flex-none" onClick={() => void navigator.clipboard.writeText(message).then(() => setOpened(true))}><Copy />Copiar mensagem</Button>}
        <Button type="button" size="lg" variant={opened ? "default" : "outline"} disabled={saving} onClick={() => void markSent()}>{saving ? <Loader2 className="animate-spin" /> : <Check />}Enviei</Button>
        <Button type="button" variant="ghost" aria-label="Pular" className="px-2 text-muted-foreground sm:ml-auto" onClick={() => setIndex((value) => (value + 1) % Math.max(1, pending.length))}><SkipForward /><span className="hidden sm:inline">Pular</span></Button>
      </div>
      {!link ? <p className="text-xs text-muted-foreground">Este lead não tem WhatsApp público: copie a mensagem e use outro canal.</p> : null}
    </section>
  </div>
}
