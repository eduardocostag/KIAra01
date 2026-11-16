"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Check, Copy, Crown, Gem, Loader2, MessageCircle, Trash2, Trophy, UserPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { growth, type PlanOverview, type TeamOverview } from "@/lib/api/growth"
import { cn } from "@/lib/utils"

const field = "h-10 rounded-md border bg-background px-3 text-sm outline-none focus:border-primary/50"
const money = (cents: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(cents / 100)

export function TeamWorkspace() {
  const [data, setData] = useState<TeamOverview | null>(null)
  const [error, setError] = useState("")
  const [link, setLink] = useState("")
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const load = useCallback(() => growth<TeamOverview>("team").then(setData).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar.")), [])
   
  useEffect(() => { void load() }, [load])

  async function run(work: () => Promise<unknown>) {
    setBusy(true); setError("")
    try { await work(); await load() } catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível concluir.") } finally { setBusy(false) }
  }

  if (!data) return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : <div className="fx-skeleton h-40 rounded-2xl" />
  const leader = data.ranking[0]
  return <div className="space-y-6">
    {error ? <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}
    <section aria-labelledby="ranking" className="kiara-soft-panel rounded-2xl border p-5 sm:p-6">
      <h2 id="ranking" className="flex items-center gap-2 text-lg font-semibold"><Trophy className="size-5 text-amber-400" aria-hidden="true" />Ranking dos últimos 30 dias</h2>
      <table className="mt-3 w-full text-sm"><caption className="sr-only">Vendas e abordagens por pessoa</caption>
        <thead><tr className="text-left text-xs text-muted-foreground"><th scope="col" className="py-2">Pessoa</th><th scope="col" className="py-2 text-right">Abordagens</th><th scope="col" className="py-2 text-right">Vendas</th></tr></thead>
        <tbody>{data.ranking.map((person, position) => <tr key={person.subject} className="border-t">
          <td className="py-2.5"><span className="inline-flex items-center gap-2">{position === 0 && leader && (leader.won || leader.approached) ? <Crown className="size-4 text-amber-400" aria-label="Primeiro lugar" /> : <span className="w-4 text-center text-xs text-muted-foreground">{position + 1}</span>}{person.display_name || person.email || "Dono da conta"}{person.you ? <span className="text-xs text-muted-foreground">(você)</span> : null}</span></td>
          <td className="py-2.5 text-right tabular-nums">{person.approached}</td><td className="py-2.5 text-right font-semibold tabular-nums">{person.won}</td>
        </tr>)}</tbody></table>
    </section>

    <section aria-labelledby="members" className="kiara-soft-panel space-y-4 rounded-2xl border p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2"><h2 id="members" className="flex-1 text-lg font-semibold">Pessoas</h2><span className="text-xs text-muted-foreground">{data.seats.used} de {data.seats.limit} lugares do plano</span></div>
      <ul className="divide-y rounded-xl border">{data.members.map((person) => <li key={person.subject} className="flex flex-wrap items-center gap-3 p-3 text-sm">
        <span className="min-w-0 flex-1"><span className="block truncate font-medium">{person.display_name || person.email || "Dono da conta"}</span>{person.email ? <span className="text-xs text-muted-foreground">{person.email}</span> : null}</span>
        {data.can_manage && person.role !== "owner" ? <select aria-label={`Papel de ${person.email}`} defaultValue={person.role} className={cn(field, "h-8")} onChange={(event) => void run(() => growth(`team/members/${person.subject}`, { method: "PATCH", body: JSON.stringify({ role: event.target.value }) }))}>
          <option value="admin">Administrador</option><option value="operator">Vendedor</option><option value="viewer">Somente leitura</option></select> : <span className="text-xs text-muted-foreground">{person.role_label}</span>}
        {data.can_manage && person.role !== "owner" ? <button type="button" aria-label={`Remover ${person.email}`} disabled={busy} onClick={() => void run(() => growth(`team/members/${person.subject}`, { method: "DELETE" }))} className="text-muted-foreground hover:text-destructive"><Trash2 className="size-4" /></button> : null}
      </li>)}
        {data.invites.map((invite) => <li key={invite.id} className="flex flex-wrap items-center gap-3 p-3 text-sm text-muted-foreground"><span className="flex-1">{invite.email} · convite pendente ({invite.role_label})</span>
          {data.can_manage ? <button type="button" disabled={busy} onClick={() => void run(() => growth(`team/invites/${invite.id}`, { method: "DELETE" }))} className="text-xs hover:text-destructive">Cancelar</button> : null}</li>)}
      </ul>
      {data.can_manage ? <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget)
        void run(async () => { const result = await growth<{ token: string }>("team/invites", { method: "POST", body: JSON.stringify({ email: form.get("email"), role: form.get("role") }) }); setLink(`${window.location.origin}/app/convite?token=${encodeURIComponent(result.token)}`); setCopied(false) }) }}>
        <label className="grid flex-1 basis-full gap-1 text-sm sm:basis-56">E-mail da pessoa<input name="email" type="email" required className={cn(field, "w-full")} placeholder="vendedor@empresa.com" /></label>
        <label className="grid flex-1 gap-1 text-sm sm:flex-none">Papel<select name="role" defaultValue="operator" className={cn(field, "w-full")}><option value="operator">Vendedor</option><option value="admin">Administrador</option><option value="viewer">Somente leitura</option></select></label>
        <Button type="submit" disabled={busy}>{busy ? <Loader2 className="animate-spin" /> : <UserPlus />}Convidar</Button>
      </form> : null}
      {link ? <div className="space-y-2 rounded-xl border border-primary/40 bg-primary/10 p-3 text-sm">
        <p className="font-medium">Convite criado. Envie este link para a pessoa (vale por 7 dias e só uma vez):</p>
        <p className="break-all rounded-md bg-background/60 p-2 font-mono text-xs">{link}</p>
        <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" onClick={() => void navigator.clipboard.writeText(link).then(() => setCopied(true))}>{copied ? <Check /> : <Copy />}{copied ? "Copiado" : "Copiar link"}</Button>
          <Button asChild size="sm" variant="outline"><a href={`https://wa.me/?text=${encodeURIComponent(`Você foi convidado para a equipe na Kiara: ${link}`)}`} target="_blank" rel="noopener noreferrer"><MessageCircle />Enviar pelo WhatsApp</a></Button></div>
      </div> : null}
    </section>
  </div>
}

export function PlanWorkspace() {
  const [data, setData] = useState<PlanOverview | null>(null)
  const [trialDays, setTrialDays] = useState<number | null>(null)
  const [error, setError] = useState("")
  useEffect(() => { growth<PlanOverview>("billing/plan").then((value) => {
    setData(value)
    setTrialDays(value.trial_ends_at ? Math.max(0, Math.ceil((new Date(value.trial_ends_at).getTime() - Date.now()) / 86_400_000)) : null)
  }).catch((reason) => setError(reason instanceof Error ? reason.message : "Não foi possível carregar.")) }, [])
  if (!data) return error ? <p role="alert" className="text-sm text-destructive">{error}</p> : <div className="fx-skeleton h-40 rounded-2xl" />
  return <div className="space-y-6">
    <section aria-labelledby="current-plan" className="kiara-soft-panel space-y-4 rounded-2xl border p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-3"><Gem className="size-6 text-primary" aria-hidden="true" /><div className="flex-1"><h2 id="current-plan" className="text-lg font-semibold">Plano {data.label}</h2>
        <p className="text-sm text-muted-foreground">{data.plan === "trial" && trialDays !== null ? `${trialDays} dia${trialDays === 1 ? "" : "s"} de teste restante${trialDays === 1 ? "" : "s"}` : data.status === "active" ? "Ativo" : "Pagamento pendente"} · uso deste mês</p></div></div>
      <ul className="grid gap-3 sm:grid-cols-2">{data.usage.map((item) => { const percent = Math.min(100, Math.round((item.used / Math.max(1, item.limit)) * 100)); return <li key={item.metric} className="space-y-1.5">
        <div className="flex text-sm"><span className="flex-1 first-letter:uppercase">{item.label}</span><span className="tabular-nums text-muted-foreground">{item.used} de {item.limit}</span></div>
        <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={item.label} aria-valuenow={item.used} aria-valuemax={item.limit}><div className={cn("h-full rounded-full", percent >= 90 ? "bg-rose-400" : percent >= 70 ? "bg-amber-400" : "bg-primary")} style={{ width: `${percent}%` }} /></div>
      </li> })}</ul>
    </section>
    <section aria-labelledby="plans" className="grid gap-4 md:grid-cols-3">{data.plans.map((plan) => <div key={plan.id} className={cn("kiara-soft-panel flex flex-col rounded-2xl border p-5", plan.id === data.plan && "border-primary/60")}>
      <h3 id={plan.id === "pro" ? "plans" : undefined} className="text-base font-semibold">{plan.label}</h3>
      <p className="mt-1 text-2xl font-semibold">{money(plan.price_cents)}<span className="text-sm font-normal text-muted-foreground">/mês</span></p>
      <ul className="mt-3 flex-1 space-y-1 text-sm text-muted-foreground">
        <li>Leads ilimitados</li><li>{plan.limits.ai_messages.toLocaleString("pt-BR")} mensagens escritas pela Kiara</li>
        <li>{plan.limits.images.toLocaleString("pt-BR")} imagens e {plan.limits.videos} vídeos</li><li>{plan.limits.seats} {plan.limits.seats === 1 ? "pessoa" : "pessoas"} na equipe</li></ul>
      <Button className="mt-4" variant={plan.id === data.plan ? "outline" : "default"} disabled={plan.id === data.plan} asChild={plan.id !== data.plan}>
        {plan.id === data.plan ? <span>Plano atual</span> : <a href={`https://wa.me/${(process.env.NEXT_PUBLIC_KIARA_SALES_WHATSAPP ?? "").replace(/\D/g, "")}?text=${encodeURIComponent(`Quero assinar o plano ${plan.label} da Kiara.`)}`} target="_blank" rel="noopener noreferrer">Quero este plano</a>}
      </Button>
    </div>)}</section>
    {!data.billing_connected ? <p className="text-xs text-muted-foreground">O pagamento online (Pix e cartão) chega em breve. Por enquanto, a mudança de plano é feita pelo nosso atendimento.</p> : null}
  </div>
}

export function AcceptInvite({ token }: { token: string }) {
  const router = useRouter()
  const [state, setState] = useState<"idle" | "busy" | "done">("idle")
  const [error, setError] = useState("")
  async function accept(form: FormData) {
    setState("busy"); setError("")
    try { await growth("team/accept", { method: "POST", body: JSON.stringify({ token, display_name: form.get("name") || "" }) }); setState("done"); setTimeout(() => router.push("/app/fila"), 1200) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Não foi possível aceitar."); setState("idle") }
  }
  if (!token) return <p className="text-sm text-destructive">Link de convite incompleto. Peça um novo link.</p>
  return <form action={(form) => void accept(form)} className="kiara-soft-panel mx-auto max-w-md space-y-4 rounded-2xl border p-6">
    <h1 className="text-2xl font-medium tracking-tight">Entrar na equipe</h1>
    <p className="text-sm text-muted-foreground">Você foi convidado para trabalhar na conta de uma empresa na Kiara. Seus próprios dados continuam separados.</p>
    <label className="grid gap-1 text-sm">Como você quer aparecer para a equipe<input name="name" className={field} maxLength={160} placeholder="Seu nome" /></label>
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    {state === "done" ? <p role="status" className="flex items-center gap-2 text-sm text-emerald-400"><Check className="size-4" />Pronto! Abrindo a fila de hoje…</p>
      : <Button type="submit" disabled={state === "busy"} className="w-full">{state === "busy" ? <Loader2 className="animate-spin" /> : <UserPlus />}Aceitar convite</Button>}
    <p className="text-center text-xs"><Link href="/app" className="text-muted-foreground hover:underline">Agora não</Link></p>
  </form>
}
