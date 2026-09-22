"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { ArrowRight, CheckCircle2, Clock3, LoaderCircle, Save, Timer, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { leadDisplayName, type PipelineEntry } from "@/lib/api/pipeline"
import { salesRequest, type SalesProfile } from "@/lib/api/sales"

function dueLabel(value: string, now: number) {
  const date = new Date(value)
  if (date.getTime() < now) return "Vencido"
  if (date.toDateString() === new Date(now).toDateString()) return "Hoje"
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(date)
}

export function FollowUpsWorkspace({ entries }: { entries: PipelineEntry[] }) {
  const [profile, setProfile] = useState<SalesProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)
  const [hours, setHours] = useState(48)
  const [followUp, setFollowUp] = useState("")
  const [reactivation, setReactivation] = useState("")
  const [now] = useState(() => Date.now())
  const reminders = entries.filter((entry) => entry.next_action_at && !["won", "lost"].includes(entry.stage)).sort((a, b) => new Date(a.next_action_at!).getTime() - new Date(b.next_action_at!).getTime())
  const overdue = reminders.filter((entry) => new Date(entry.next_action_at!).getTime() < now).length

  useEffect(() => {
    void salesRequest<SalesProfile>("/api/sales/profile").then((value) => {
      setProfile(value); setHours(value.follow_up_hours); setFollowUp(value.templates.follow_up ?? ""); setReactivation(value.templates.reactivation ?? "")
    }).catch((error) => setNotice({ ok: false, text: error instanceof Error ? error.message : "Não foi possível carregar as configurações." })).finally(() => setLoading(false))
  }, [])

  async function save() {
    if (!profile) return
    setSaving(true); setNotice(null)
    try {
      const templates = { ...profile.templates, follow_up: followUp.trim(), reactivation: reactivation.trim() }
      const saved = await salesRequest<SalesProfile>("/api/sales/profile", { method: "PUT", body: JSON.stringify({ business_name: profile.business_name, sender_name: profile.sender_name, offer: profile.offer, tone: profile.tone, follow_up_hours: hours, contact_start: profile.contact_start, contact_end: profile.contact_end, templates }) })
      setProfile(saved); setFollowUp(saved.templates.follow_up ?? ""); setReactivation(saved.templates.reactivation ?? ""); setNotice({ ok: true, text: "Configuração de follow-up salva neste workspace." })
    } catch (error) { setNotice({ ok: false, text: error instanceof Error ? error.message : "Não foi possível salvar a configuração." }) }
    finally { setSaving(false) }
  }

  return <div className="mx-auto max-w-6xl space-y-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-primary">Rotina comercial</p><h1 className="kiara-editorial mt-2 text-4xl">Follow-ups</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Organize os próximos contatos e mantenha uma mensagem consistente depois da primeira abordagem.</p></div><Button asChild variant="outline"><Link href="/app/inbox?view=pipeline">Abrir Pipeline<ArrowRight /></Link></Button></header>
    {notice && <div role="alert" className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${notice.ok ? "border-emerald-500/25 bg-emerald-500/5" : "border-destructive/25 bg-destructive/5"}`}>{notice.ok ? <CheckCircle2 className="mt-0.5 size-4 text-emerald-600" /> : <TriangleAlert className="mt-0.5 size-4 text-destructive" />}<span>{notice.text}</span></div>}
    <section className="grid gap-4 sm:grid-cols-3" aria-label="Resumo dos follow-ups"><Summary icon={<Timer />} label="Agendados" value={reminders.length} /><Summary icon={<Clock3 />} label="Vencidos" value={overdue} danger={overdue > 0} /><Summary icon={<CheckCircle2 />} label="Prazo padrão" value={`${hours}h`} /></section>
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="overflow-hidden rounded-2xl border bg-card"><div className="border-b p-5"><h2 className="font-semibold">Fila de lembretes</h2><p className="mt-1 text-sm text-muted-foreground">Ações ordenadas pela data em que precisam acontecer.</p></div>{reminders.length ? <ul className="divide-y">{reminders.map((entry) => { const isOverdue = new Date(entry.next_action_at!).getTime() < now; return <li key={entry.id} className="flex items-center gap-3 p-4"><span className={`size-2 shrink-0 rounded-full ${isOverdue ? "bg-destructive" : "bg-primary"}`} /><div className="min-w-0 flex-1"><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} className="font-semibold hover:text-primary">{leadDisplayName(entry.consumer)}</Link><p className="mt-1 truncate text-sm text-muted-foreground">{entry.next_action || "Revisar oportunidade"}</p></div><time className={`shrink-0 text-xs font-medium ${isOverdue ? "text-destructive" : "text-muted-foreground"}`} dateTime={entry.next_action_at!}>{dueLabel(entry.next_action_at!, now)}</time><Link href={`/app/leads/${encodeURIComponent(entry.consumer.id)}`} aria-label={`Abrir ${leadDisplayName(entry.consumer)}`} className="text-muted-foreground hover:text-primary"><ArrowRight className="size-4" /></Link></li> })}</ul> : <div className="grid min-h-52 place-items-center p-6 text-center text-sm text-muted-foreground"><div><Clock3 className="mx-auto mb-3 size-6 text-primary" /><p>Nenhum follow-up agendado.</p><Link href="/app/inbox?view=pipeline" className="mt-3 inline-flex items-center gap-1 font-semibold text-primary">Revisar Pipeline<ArrowRight className="size-3.5" /></Link></div></div>}</div>
      <div className="rounded-2xl border bg-card p-5"><div className="mb-5"><h2 className="font-semibold">Configurar lembretes</h2><p className="mt-1 text-sm leading-5 text-muted-foreground">Esse prazo é usado quando você confirma que enviou uma abordagem.</p></div>{loading ? <div className="grid min-h-48 place-items-center"><LoaderCircle className="animate-spin" /></div> : profile ? <div className="space-y-5"><div className="grid gap-2"><Label htmlFor="follow-up-hours">Lembrar depois de</Label><div className="flex items-center gap-2"><Input id="follow-up-hours" type="number" min={1} max={720} value={hours} onChange={(event) => setHours(Math.max(1, Math.min(720, Number(event.target.value) || 1)))} /><span className="text-sm text-muted-foreground">horas</span></div></div><div className="grid gap-2"><Label htmlFor="follow-up-message">Mensagem de follow-up</Label><Textarea id="follow-up-message" value={followUp} onChange={(event) => setFollowUp(event.target.value)} maxLength={20000} className="min-h-32 resize-y" /><p className="text-xs text-muted-foreground">Use variáveis como {'{nome}'}, {'{remetente}'} e {'{oferta}'}.</p></div><div className="grid gap-2"><Label htmlFor="reactivation-message">Mensagem de reativação</Label><Textarea id="reactivation-message" value={reactivation} onChange={(event) => setReactivation(event.target.value)} maxLength={20000} className="min-h-32 resize-y" /></div><Button className="w-full" onClick={() => void save()} disabled={saving}>{saving ? <LoaderCircle className="animate-spin" /> : <Save />}Salvar configuração</Button></div> : null}</div>
    </section>
  </div>
}

function Summary({ icon, label, value, danger = false }: { icon: React.ReactNode; label: string; value: string | number; danger?: boolean }) { return <div className="flex items-center gap-3 rounded-2xl border bg-card p-4"><span className={`grid size-10 place-items-center rounded-xl ${danger ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary"}`}>{icon}</span><div><strong className="text-2xl tabular-nums">{value}</strong><p className="text-xs text-muted-foreground">{label}</p></div></div> }
